#!/usr/bin/env python3
import os
import math
import yaml
import copy
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

CONFIG_FILE = "cfg.yaml"

class WallBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Mundo Gazebo - Paredes e Meshes")
        self.root.resizable(False, False)
        
        self.arena_w = 20.0
        self.arena_h = 20.0
        self.arena_offset_x = 0.0
        self.arena_offset_y = 0.0
        self.scale = 20.0
        
        self.wall_height = 0.5 
        self.wall_thickness = 0.2
        self.wall_color = "black" 

        self.start_point = None
        self.walls = []  
        self.placed_meshes = [] 
        self.mesh_folder = ""
        self.last_direction_angle = 0.0
        
        self.slam_image_original = None
        self.slam_image_path = ""
        self.slam_resolution = 0.05
        self.map_rotation = 0.0
        self.bg_photo = None

        self.history = []
        self.max_history = 7
        self.root.bind("<Control-z>", self.undo)

        self.canvas_size = 700
        self.canvas = tk.Canvas(root, width=self.canvas_size, height=self.canvas_size, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        panel = tk.Frame(root, width=280)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self.mode = tk.StringVar(value="wall")
        ttk.Radiobutton(panel, text="Modo: Desenhar Paredes", variable=self.mode, value="wall").pack(anchor="w", pady=2)
        ttk.Radiobutton(panel, text="Modo: Inserir Mesh", variable=self.mode, value="mesh").pack(anchor="w", pady=2)
        
        self.snap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Snap de Ângulo (15°, 30°...)", variable=self.snap_var).pack(anchor="w", pady=(5, 0))
        
        self.snap_wall_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Snap em Paredes (Cantos/Linhas)", variable=self.snap_wall_var).pack(anchor="w", pady=(0, 5))

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=5)

        arena_frame = tk.LabelFrame(panel, text="Arena & Mapa (Metros)")
        arena_frame.pack(fill=tk.X, pady=5, ipadx=5, ipady=5)
        
        tk.Button(arena_frame, text="Carregar Mapa SLAM (YAML)", command=self.load_slam_map, bg="#d4e1f9").grid(row=0, column=0, columnspan=2, pady=5, sticky="ew")
        
        tk.Label(arena_frame, text="Largura (X):").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.entry_arena_w = tk.Entry(arena_frame, width=10)
        self.entry_arena_w.insert(0, str(self.arena_w))
        self.entry_arena_w.grid(row=1, column=1, padx=5, pady=2)
        
        tk.Label(arena_frame, text="Altura (Y):").grid(row=2, column=0, padx=5, pady=2, sticky="e")
        self.entry_arena_h = tk.Entry(arena_frame, width=10)
        self.entry_arena_h.insert(0, str(self.arena_h))
        self.entry_arena_h.grid(row=2, column=1, padx=5, pady=2)

        tk.Label(arena_frame, text="Rotação Mapa (°):").grid(row=3, column=0, padx=5, pady=2, sticky="e")
        self.entry_map_rot = tk.Entry(arena_frame, width=10)
        self.entry_map_rot.insert(0, str(self.map_rotation))
        self.entry_map_rot.grid(row=3, column=1, padx=5, pady=2)
        
        tk.Button(arena_frame, text="Atualizar Arena", command=self.update_arena_size).grid(row=4, column=0, columnspan=2, pady=5, sticky="ew")

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=5)

        self.lbl_length = tk.Label(panel, text="Tamanho da parede: 0.00 m", font=("Arial", 10, "bold"), fg="blue")
        self.lbl_length.pack(pady=5)

        tk.Label(panel, text="Comprimento Exato (m):").pack(anchor="w")
        tk.Label(panel, text="Aponte o mouse e aperte Enter", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w")
        self.entry_exact_length = tk.Entry(panel)
        self.entry_exact_length.pack(fill=tk.X, pady=5)
        self.entry_exact_length.bind("<Return>", self.apply_exact_length)

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=5)

        tk.Button(panel, text="Carregar Pasta de Meshes", command=self.load_mesh_folder).pack(fill=tk.X, pady=5)
        
        self.mesh_var = tk.StringVar()
        self.mesh_dropdown = ttk.Combobox(panel, textvariable=self.mesh_var, state="readonly")
        self.mesh_dropdown.pack(fill=tk.X, pady=5)
        
        tk.Label(panel, text="Rotação Yaw (graus):").pack(anchor="w")
        self.entry_yaw = tk.Entry(panel)
        self.entry_yaw.insert(0, "0.0")
        self.entry_yaw.pack(fill=tk.X, pady=2)
        
        tk.Label(panel, text="Altura Z (m):").pack(anchor="w")
        self.entry_z = tk.Entry(panel)
        self.entry_z.insert(0, "0.0")
        self.entry_z.pack(fill=tk.X, pady=2)

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=10)

        btn_frame = tk.Frame(panel)
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="Desfazer (Ctrl+Z)", command=self.undo, bg="#e0e0e0").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(btn_frame, text="Limpar Tudo", command=self.clear_canvas, bg="#ffcccc").pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))
        
        tk.Button(panel, text="Salvar Configs e Mundo", command=self.save_all, bg="#ccffcc", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=10)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_move)

        self.load_config()
        self.update_arena_size(force_redraw=False)

    def load_slam_map(self):
        if not HAS_PIL:
            messagebox.showerror("Erro", "A biblioteca 'Pillow' não está instalada.\nAbra o terminal e digite: pip3 install Pillow")
            return
            
        yaml_path = filedialog.askopenfilename(title="Selecione o YAML do Mapa SLAM", filetypes=[("YAML", "*.yaml *.yml")])
        if not yaml_path:
            return
            
        try:
            with open(yaml_path, 'r') as f:
                map_data = yaml.safe_load(f)
                
            img_file = map_data.get('image')
            res = float(map_data.get('resolution', 0.05))
            origin = map_data.get('origin', [0, 0, 0])
            
            if not img_file:
                messagebox.showerror("Erro", "O YAML não contém a chave 'image'.")
                return
                
            img_path = os.path.join(os.path.dirname(yaml_path), img_file)
            if not os.path.exists(img_path):
                messagebox.showerror("Erro", f"Imagem não encontrada no diretório do YAML:\n{img_path}")
                return
                
            self.slam_image_path = img_path
            self.slam_image_original = Image.open(img_path)
            self.slam_resolution = res
            
            self.arena_w = self.slam_image_original.width * res
            self.arena_h = self.slam_image_original.height * res
            
            self.arena_offset_x = origin[0] + (self.arena_w / 2.0)
            self.arena_offset_y = origin[1] + (self.arena_h / 2.0)
            
            self.map_rotation = 0.0
            self.wall_color = "cyan"
            
            self.entry_arena_w.delete(0, tk.END)
            self.entry_arena_w.insert(0, f"{self.arena_w:.2f}")
            self.entry_arena_h.delete(0, tk.END)
            self.entry_arena_h.insert(0, f"{self.arena_h:.2f}")
            self.entry_map_rot.delete(0, tk.END)
            self.entry_map_rot.insert(0, "0.0")
            
            self.update_arena_size(force_redraw=True)
            messagebox.showinfo("Sucesso", f"Mapa SLAM carregado com sucesso!\nTamanho Real: {self.arena_w:.2f}m x {self.arena_h:.2f}m")
            
        except Exception as e:
            messagebox.showerror("Erro ao carregar mapa", str(e))

    def draw_background(self):
        self.canvas.delete("bg_image")
        if self.slam_image_original and HAS_PIL:
            try:
                map_w_m = self.slam_image_original.width * self.slam_resolution
                map_h_m = self.slam_image_original.height * self.slam_resolution
                
                px_w = int(map_w_m * self.scale)
                px_h = int(map_h_m * self.scale)
                
                if px_w > 0 and px_h > 0:
                    resample_filter = getattr(Image, 'Resampling', Image).NEAREST
                    
                    resized = self.slam_image_original.resize((px_w, px_h), resample_filter)
                    
                    rotated = resized.rotate(self.map_rotation, expand=True, resample=resample_filter)
                    
                    self.bg_photo = ImageTk.PhotoImage(rotated)
                    
                    cx, cy = self.canvas_size / 2.0, self.canvas_size / 2.0
                    
                    self.canvas.create_image(cx, cy, image=self.bg_photo, tags="bg_image")
                    self.canvas.tag_lower("bg_image")
            except Exception as e:
                print(f"Erro ao desenhar fundo: {e}")

    def save_state_to_history(self):
        state = {
            'walls': list(self.walls),
            'meshes': [m.copy() for m in self.placed_meshes]
        }
        self.history.append(state)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def undo(self, event=None):
        if self.mode.get() == "wall" and self.start_point is not None:
            self.start_point = None
            self.canvas.delete("preview")
            self.lbl_length.config(text="Tamanho da parede: 0.00 m")
            self.entry_exact_length.delete(0, tk.END)
            return

        if not self.history:
            return 

        last_state = self.history.pop()
        self.walls = list(last_state['walls'])
        self.placed_meshes = [m.copy() for m in last_state['meshes']]
        
        self.canvas.delete("wall", "mesh_marker", "preview", "snap_indicator")
        self.redraw_all()

    def snap_to_walls(self, x, y):
        threshold = 15.0 / self.scale 
        closest_dist = float('inf')
        snapped_x, snapped_y = x, y
        
        for w_x1, w_y1, w_x2, w_y2 in self.walls:
            for cx, cy in [(w_x1, w_y1), (w_x2, w_y2)]:
                d = math.hypot(cx - x, cy - y)
                if d < threshold and d < closest_dist:
                    closest_dist = d - 0.01 
                    snapped_x, snapped_y = cx, cy

            dx = w_x2 - w_x1
            dy = w_y2 - w_y1
            l2 = dx*dx + dy*dy
            if l2 == 0: continue
            
            t = ((x - w_x1) * dx + (y - w_y1) * dy) / l2
            t = max(0, min(1, t)) 
            
            proj_x = w_x1 + t * dx
            proj_y = w_y1 + t * dy
            
            d_line = math.hypot(proj_x - x, proj_y - y)
            if d_line < threshold and d_line < closest_dist:
                closest_dist = d_line
                snapped_x, snapped_y = proj_x, proj_y
                
        return snapped_x, snapped_y, closest_dist < threshold

    def px_to_m(self, px, py):
        cx, cy = self.canvas_size / 2.0, self.canvas_size / 2.0
        x = (px - cx) / self.scale + self.arena_offset_x
        y = -(py - cy) / self.scale + self.arena_offset_y
        return x, y

    def m_to_px(self, x, y):
        cx, cy = self.canvas_size / 2.0, self.canvas_size / 2.0
        px = ((x - self.arena_offset_x) * self.scale) + cx
        py = -((y - self.arena_offset_y) * self.scale) + cy
        return px, py

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    
                    self.arena_w = float(config.get('arena_w', 20.0))
                    self.arena_h = float(config.get('arena_h', 20.0))
                    self.arena_offset_x = float(config.get('arena_offset_x', 0.0))
                    self.arena_offset_y = float(config.get('arena_offset_y', 0.0))
                    self.map_rotation = float(config.get('map_rotation', 0.0))
                    self.slam_resolution = float(config.get('slam_resolution', 0.05))
                    self.slam_image_path = config.get('slam_image_path', "")
                    
                    self.entry_arena_w.delete(0, tk.END)
                    self.entry_arena_w.insert(0, str(self.arena_w))
                    self.entry_arena_h.delete(0, tk.END)
                    self.entry_arena_h.insert(0, str(self.arena_h))
                    self.entry_map_rot.delete(0, tk.END)
                    self.entry_map_rot.insert(0, str(self.map_rotation))

                    # Restaura o mapa de fundo se existir
                    if self.slam_image_path and os.path.exists(self.slam_image_path) and HAS_PIL:
                        self.slam_image_original = Image.open(self.slam_image_path)
                        self.wall_color = "cyan"

                    saved_folder = config.get('mesh_folder', '')
                    if saved_folder and os.path.isdir(saved_folder):
                        self.mesh_folder = saved_folder
                        self.update_mesh_dropdown()
                    
                    loaded_walls = config.get('walls', [])
                    self.walls = [tuple(w) for w in loaded_walls]
                    self.placed_meshes = config.get('placed_meshes', [])
            except Exception as e:
                print(f"Erro ao carregar config: {e}")

    def save_config(self):
        config = {
            'arena_w': self.arena_w,
            'arena_h': self.arena_h,
            'arena_offset_x': self.arena_offset_x,
            'arena_offset_y': self.arena_offset_y,
            'map_rotation': self.map_rotation,
            'slam_resolution': self.slam_resolution,
            'slam_image_path': self.slam_image_path,
            'mesh_folder': self.mesh_folder,
            'walls': self.walls,
            'placed_meshes': self.placed_meshes
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.safe_dump(config, f)
        except Exception as e:
            print(f"Erro ao salvar config: {e}")

    def save_all(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(base_dir, "results")
        os.makedirs(results_dir, exist_ok=True)
        
        sdf_path = os.path.join(results_dir, "mundo_gerado.sdf")
        with open(sdf_path, "w") as f:
            f.write(self.generate_sdf())
            
        self.save_config()
        messagebox.showinfo("Sucesso", f"Progresso salvo no cfg.yaml!\n\nMundo exportado em:\n{sdf_path}")

    def update_arena_size(self, force_redraw=True):
        try:
            w = float(self.entry_arena_w.get())
            h = float(self.entry_arena_h.get())
            rot = float(self.entry_map_rot.get())
            
            if w <= 0 or h <= 0:
                raise ValueError
            
            self.arena_w = w
            self.arena_h = h
            self.map_rotation = rot
            
            available_px = self.canvas_size - 40
            self.scale = min(available_px / self.arena_w, available_px / self.arena_h)
            
            self.draw_grid()
            self.draw_background() 
            
            if force_redraw:
                self.canvas.delete("wall", "mesh_marker")
                self.redraw_all()
                
        except ValueError:
            messagebox.showerror("Erro", "Insira valores numéricos para tamanho/rotação da arena.")

    def redraw_all(self):
        for (x1, y1, x2, y2) in self.walls:
            px1, py1 = self.m_to_px(x1, y1)
            px2, py2 = self.m_to_px(x2, y2)
            self.canvas.create_line(px1, py1, px2, py2, width=4, fill=self.wall_color, tags="wall")
            
        for m in self.placed_meshes:
            px, py = self.m_to_px(m['x'], m['y'])
            r = 6
            self.canvas.create_oval(px - r, py - r, px + r, py + r, fill="orange", tags="mesh_marker")
            mesh_name = os.path.basename(m['file'])[:5] + ".."
            self.canvas.create_text(px, py - 12, text=mesh_name, font=("Arial", 7), tags="mesh_marker")

    def draw_grid(self):
        self.canvas.delete("grid", "arena_border")
        
        min_x = self.arena_offset_x - (self.arena_w / 2.0)
        max_x = self.arena_offset_x + (self.arena_w / 2.0)
        min_y = self.arena_offset_y - (self.arena_h / 2.0)
        max_y = self.arena_offset_y + (self.arena_h / 2.0)
        
        px_min_x, px_max_y = self.m_to_px(min_x, min_y)
        px_max_x, px_min_y = self.m_to_px(max_x, max_y)
        
        self.canvas.create_rectangle(px_min_x, px_min_y, px_max_x, px_max_y, fill="", outline="#3b82f6", width=2, tags="arena_border")
        
        start_x = math.ceil(min_x)
        end_x = math.floor(max_x)
        for x in range(start_x, end_x + 1):
            px, _ = self.m_to_px(x, 0)
            color = "#a0a0a0" if x == 0 else "#e0e0e0"
            width = 2 if x == 0 else 1
            self.canvas.create_line(px, px_min_y, px, px_max_y, fill=color, width=width, tags="grid")

        start_y = math.ceil(min_y)
        end_y = math.floor(max_y)
        for y in range(start_y, end_y + 1):
            _, py = self.m_to_px(0, y)
            color = "#a0a0a0" if y == 0 else "#e0e0e0"
            width = 2 if y == 0 else 1
            self.canvas.create_line(px_min_x, py, px_max_x, py, fill=color, width=width, tags="grid")

        self.canvas.tag_lower("grid")
        self.canvas.tag_lower("arena_border")

    def update_mesh_dropdown(self):
        files = [f for f in os.listdir(self.mesh_folder) if f.lower().endswith(('.dae', '.stl', '.obj'))]
        self.mesh_dropdown['values'] = files
        if files:
            self.mesh_dropdown.current(0)

    def load_mesh_folder(self):
        folder = filedialog.askdirectory(title="Selecione a pasta com os Meshes 3D")
        if folder:
            self.mesh_folder = folder
            self.update_mesh_dropdown()

    def get_snapped_endpoint(self, x1, y1, raw_x2, raw_y2):
        if self.snap_wall_var.get():
            snap_x, snap_y, did_snap = self.snap_to_walls(raw_x2, raw_y2)
            if did_snap:
                length = math.hypot(snap_x - x1, snap_y - y1)
                angle = math.atan2(snap_y - y1, snap_x - x1)
                return snap_x, snap_y, length, angle
                
        length = math.hypot(raw_x2 - x1, raw_y2 - y1)
        angle = math.atan2(raw_y2 - y1, raw_x2 - x1)
        
        if self.snap_var.get():
            snap_rad = math.radians(15) 
            angle = round(angle / snap_rad) * snap_rad
            
        x2 = x1 + length * math.cos(angle)
        y2 = y1 + length * math.sin(angle)
        return x2, y2, length, angle

    def on_click(self, event):
        if self.mode.get() == "wall":
            if self.start_point is None:
                x, y = self.px_to_m(event.x, event.y)
                if self.snap_wall_var.get():
                    x, y, _ = self.snap_to_walls(x, y)
                px, py = self.m_to_px(x, y)
                
                self.start_point = (px, py)
                self.entry_exact_length.delete(0, tk.END)
                self.entry_exact_length.focus_set()
            else:
                x1, y1 = self.px_to_m(self.start_point[0], self.start_point[1])
                raw_x2, raw_y2 = self.px_to_m(event.x, event.y)
                
                x2, y2, length, _ = self.get_snapped_endpoint(x1, y1, raw_x2, raw_y2)
                
                if length > 0.05:
                    self.save_state_to_history() 
                    self.walls.append((x1, y1, x2, y2))
                    px2, py2 = self.m_to_px(x2, y2)
                    self.canvas.create_line(self.start_point[0], self.start_point[1], px2, py2, width=4, fill=self.wall_color, tags="wall")
                
                self.start_point = None
                self.canvas.delete("preview")
                self.lbl_length.config(text="Tamanho da parede: 0.00 m")
                self.canvas.focus_set()
        
        elif self.mode.get() == "mesh":
            mesh_file = self.mesh_var.get()
            if not mesh_file:
                messagebox.showwarning("Aviso", "Selecione um mesh primeiro.")
                return
            
            try:
                yaw = math.radians(float(self.entry_yaw.get()))
                z = float(self.entry_z.get())
            except ValueError:
                messagebox.showerror("Erro", "Valores de Rotação e Altura devem ser números.")
                return

            x, y = self.px_to_m(event.x, event.y)
            abs_path = os.path.join(self.mesh_folder, mesh_file)
            
            self.save_state_to_history() 
            self.placed_meshes.append({'file': abs_path, 'x': x, 'y': y, 'z': z, 'yaw': yaw})
            
            r = 6
            self.canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r, fill="orange", tags="mesh_marker")
            self.canvas.create_text(event.x, event.y - 12, text=mesh_file[:5]+"..", font=("Arial", 7), tags="mesh_marker")

    def on_move(self, event):
        self.canvas.delete("snap_indicator")
        
        raw_x, raw_y = self.px_to_m(event.x, event.y)
        if self.mode.get() == "wall" and self.snap_wall_var.get():
            snap_x, snap_y, did_snap = self.snap_to_walls(raw_x, raw_y)
            if did_snap:
                px, py = self.m_to_px(snap_x, snap_y)
                self.canvas.create_rectangle(px-5, py-5, px+5, py+5, outline="magenta", width=2, tags="snap_indicator")
                
        if self.mode.get() == "wall" and self.start_point:
            self.canvas.delete("preview")
            
            x1, y1 = self.px_to_m(self.start_point[0], self.start_point[1])
            
            x2, y2, length, angle = self.get_snapped_endpoint(x1, y1, raw_x, raw_y)
            self.last_direction_angle = angle 
            
            self.lbl_length.config(text=f"Tamanho da parede: {length:.2f} m")
            px2, py2 = self.m_to_px(x2, y2)
            self.canvas.create_line(self.start_point[0], self.start_point[1], px2, py2, width=2, dash=(4, 4), fill="red", tags="preview")

    def apply_exact_length(self, event=None):
        if self.mode.get() == "wall" and self.start_point is not None:
            try:
                exact_length = float(self.entry_exact_length.get())
            except ValueError:
                messagebox.showerror("Erro", "Digite um valor numérico válido para o comprimento.")
                return
            
            x1, y1 = self.px_to_m(self.start_point[0], self.start_point[1])
            angle = self.last_direction_angle
            
            x2 = x1 + exact_length * math.cos(angle)
            y2 = y1 + exact_length * math.sin(angle)
            
            self.save_state_to_history() 
            self.walls.append((x1, y1, x2, y2))
            px2, py2 = self.m_to_px(x2, y2)
            self.canvas.create_line(self.start_point[0], self.start_point[1], px2, py2, width=4, fill=self.wall_color, tags="wall")
            
            self.start_point = None
            self.canvas.delete("preview")
            self.lbl_length.config(text="Tamanho da parede: 0.00 m")
            self.entry_exact_length.delete(0, tk.END)
            self.canvas.focus_set()

    def clear_canvas(self):
        if self.walls or self.placed_meshes:
            self.save_state_to_history()
            
        self.walls.clear()
        self.placed_meshes.clear()
        self.start_point = None
        
        self.wall_color = "black"
        self.slam_image_original = None
        self.slam_image_path = ""
        self.map_rotation = 0.0
        self.bg_photo = None
        
        self.entry_map_rot.delete(0, tk.END)
        self.entry_map_rot.insert(0, "0.0")
        
        self.canvas.delete("wall", "preview", "mesh_marker", "snap_indicator", "bg_image")
        self.lbl_length.config(text="Tamanho da parede: 0.00 m")
        self.entry_exact_length.delete(0, tk.END)

    def generate_sdf(self):
        links_xml = ""
        for idx, (x1, y1, x2, y2) in enumerate(self.walls):
            length = math.hypot(x2 - x1, y2 - y1)
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            cz = self.wall_height / 2.0
            yaw = math.atan2(y2 - y1, x2 - x1)

            links_xml += f"""
    <link name='wall_{idx}'>
      <pose>{cx:.4f} {cy:.4f} {cz:.4f} 0 0 {yaw:.4f}</pose>
      <collision name='collision'><geometry><box><size>{length:.4f} {self.wall_thickness} {self.wall_height}</size></box></geometry></collision>
      <visual name='visual'>
        <geometry><box><size>{length:.4f} {self.wall_thickness} {self.wall_height}</size></box></geometry>
        <material><ambient>0.8 0.8 0.8 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material>
      </visual>
    </link>"""

        meshes_xml = ""
        for idx, m in enumerate(self.placed_meshes):
            meshes_xml += f"""
    <model name='custom_mesh_{idx}'>
      <static>true</static>
      <pose>{m['x']:.4f} {m['y']:.4f} {m['z']:.4f} 0 0 {m['yaw']:.4f}</pose>
      <link name='link'>
        <visual name='visual'><geometry><mesh><uri>file://{m['file']}</uri></mesh></geometry></visual>
        <collision name='collision'><geometry><mesh><uri>file://{m['file']}</uri></mesh></geometry></collision>
      </link>
    </model>"""

        return f"""<?xml version="1.0" ?>
<sdf version="1.8">
  <world name="custom_world">
    <plugin filename="ignition-gazebo-physics-system" name="ignition::gazebo::systems::Physics"/>
    <plugin filename="ignition-gazebo-user-commands-system" name="ignition::gazebo::systems::UserCommands"/>
    <plugin filename="ignition-gazebo-scene-broadcaster-system" name="ignition::gazebo::systems::SceneBroadcaster"/>
    
    <light type="directional" name="sun"><pose>0 0 10 0 0 0</pose><cast_shadows>true</cast_shadows></light>
    
    <model name="ground_plane">
      <static>true</static>
      <pose>{self.arena_offset_x:.4f} {self.arena_offset_y:.4f} -0.5 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>{self.arena_w} {self.arena_h} 1.0</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>{self.arena_w} {self.arena_h} 1.0</size></box></geometry>
          <material>
            <ambient>0.8 0.8 0.8 1</ambient>
            <diffuse>0.5 0.5 0.5 1</diffuse>
            <specular>0.1 0.1 0.1 1</specular>
          </material>
        </visual>
      </link>
    </model>

    <model name="generated_walls">
      <static>true</static>
      {links_xml}
    </model>
    {meshes_xml}
  </world>
</sdf>"""

if __name__ == "__main__":
    root = tk.Tk()
    app = WallBuilderApp(root)
    root.mainloop()