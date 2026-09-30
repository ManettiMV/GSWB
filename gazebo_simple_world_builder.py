#!/usr/bin/env python3
import os
import math
import yaml
import copy
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = "cfg.yaml"

class WallBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Mundo Gazebo - Paredes e Meshes")
        self.root.resizable(False, False)
        
        self.arena_w = 20.0
        self.arena_h = 20.0
        self.scale = 20.0
        
        self.wall_height = 0.5 
        self.wall_thickness = 0.2

        self.start_point = None
        self.walls = []  
        self.placed_meshes = [] 
        self.mesh_folder = ""
        self.last_direction_angle = 0.0

        # --- SISTEMA DE HISTÓRICO (CTRL+Z) ---
        self.history = []
        self.max_history = 7
        self.root.bind("<Control-z>", self.undo)

        self.canvas_size = 700
        self.canvas = tk.Canvas(root, width=self.canvas_size, height=self.canvas_size, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        panel = tk.Frame(root, width=280)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        # --- SEÇÃO 1: Modos e Snap ---
        self.mode = tk.StringVar(value="wall")
        ttk.Radiobutton(panel, text="Modo: Desenhar Paredes", variable=self.mode, value="wall").pack(anchor="w", pady=2)
        ttk.Radiobutton(panel, text="Modo: Inserir Mesh", variable=self.mode, value="mesh").pack(anchor="w", pady=2)
        
        self.snap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Snap de Ângulo (15°, 30°...)", variable=self.snap_var).pack(anchor="w", pady=(5, 0))
        
        # NOVA OPÇÃO: Snap em Paredes
        self.snap_wall_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Snap em Paredes (Cantos/Linhas)", variable=self.snap_wall_var).pack(anchor="w", pady=(0, 5))

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=5)

        # --- SEÇÃO 2: Tamanho da Arena ---
        arena_frame = tk.LabelFrame(panel, text="Tamanho da Arena (Metros)")
        arena_frame.pack(fill=tk.X, pady=5, ipadx=5, ipady=5)
        
        tk.Label(arena_frame, text="Largura (X):").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.entry_arena_w = tk.Entry(arena_frame, width=10)
        self.entry_arena_w.insert(0, str(self.arena_w))
        self.entry_arena_w.grid(row=0, column=1, padx=5, pady=2)
        
        tk.Label(arena_frame, text="Altura (Y):").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.entry_arena_h = tk.Entry(arena_frame, width=10)
        self.entry_arena_h.insert(0, str(self.arena_h))
        self.entry_arena_h.grid(row=1, column=1, padx=5, pady=2)
        
        tk.Button(arena_frame, text="Atualizar Arena", command=self.update_arena_size).grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=5)

        # --- SEÇÃO 3: Ferramentas de Parede ---
        self.lbl_length = tk.Label(panel, text="Tamanho da parede: 0.00 m", font=("Arial", 10, "bold"), fg="blue")
        self.lbl_length.pack(pady=5)

        tk.Label(panel, text="Comprimento Exato (m):").pack(anchor="w")
        tk.Label(panel, text="Aponte o mouse e aperte Enter", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w")
        self.entry_exact_length = tk.Entry(panel)
        self.entry_exact_length.pack(fill=tk.X, pady=5)
        self.entry_exact_length.bind("<Return>", self.apply_exact_length)

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=5)

        # --- SEÇÃO 4: Ferramentas de Mesh ---
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

        # --- BOTÕES DE AÇÃO ---
        btn_frame = tk.Frame(panel)
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="Desfazer (Ctrl+Z)", command=self.undo, bg="#e0e0e0").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(btn_frame, text="Limpar Tudo", command=self.clear_canvas, bg="#ffcccc").pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))
        
        tk.Button(panel, text="Salvar Configs e Mundo", command=self.save_all, bg="#ccffcc", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=10)

        # Binds do Canvas
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_move)

        self.load_config()
        self.update_arena_size(force_redraw=False)

    # --- FUNÇÕES DE HISTÓRICO (CTRL+Z) ---
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

    # --- LÓGICA DE SNAP NAS PAREDES ---
    def snap_to_walls(self, x, y):
        # O mouse precisa estar a um raio de 15 pixels para o snap pegar
        threshold = 15.0 / self.scale 
        closest_dist = float('inf')
        snapped_x, snapped_y = x, y
        
        for w_x1, w_y1, w_x2, w_y2 in self.walls:
            # 1. Verifica cantos primeiro (prioridade para quinas)
            for cx, cy in [(w_x1, w_y1), (w_x2, w_y2)]:
                d = math.hypot(cx - x, cy - y)
                if d < threshold and d < closest_dist:
                    closest_dist = d - 0.01 # Pequena vantagem para o canto
                    snapped_x, snapped_y = cx, cy

            # 2. Verifica pontos ao longo da linha da parede
            dx = w_x2 - w_x1
            dy = w_y2 - w_y1
            l2 = dx*dx + dy*dy
            if l2 == 0: continue
            
            # Projeta o ponto na linha da parede
            t = ((x - w_x1) * dx + (y - w_y1) * dy) / l2
            t = max(0, min(1, t)) # Garante que está no meio da parede
            
            proj_x = w_x1 + t * dx
            proj_y = w_y1 + t * dy
            
            d_line = math.hypot(proj_x - x, proj_y - y)
            if d_line < threshold and d_line < closest_dist:
                closest_dist = d_line
                snapped_x, snapped_y = proj_x, proj_y
                
        return snapped_x, snapped_y, closest_dist < threshold

    # --- OUTRAS FUNÇÕES ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    
                    self.arena_w = float(config.get('arena_w', 20.0))
                    self.arena_h = float(config.get('arena_h', 20.0))
                    self.entry_arena_w.delete(0, tk.END)
                    self.entry_arena_w.insert(0, str(self.arena_w))
                    self.entry_arena_h.delete(0, tk.END)
                    self.entry_arena_h.insert(0, str(self.arena_h))

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
            if w <= 0 or h <= 0:
                raise ValueError
            
            self.arena_w = w
            self.arena_h = h
            
            available_px = self.canvas_size - 40
            self.scale = min(available_px / self.arena_w, available_px / self.arena_h)
            
            self.draw_grid()
            
            if force_redraw:
                self.canvas.delete("wall", "mesh_marker")
                self.redraw_all()
                
        except ValueError:
            messagebox.showerror("Erro", "Insira valores numéricos positivos para a arena.")

    def redraw_all(self):
        for (x1, y1, x2, y2) in self.walls:
            px1, py1 = self.m_to_px(x1, y1)
            px2, py2 = self.m_to_px(x2, y2)
            self.canvas.create_line(px1, py1, px2, py2, width=4, fill="black", tags="wall")
            
        for m in self.placed_meshes:
            px, py = self.m_to_px(m['x'], m['y'])
            r = 6
            self.canvas.create_oval(px - r, py - r, px + r, py + r, fill="orange", tags="mesh_marker")
            mesh_name = os.path.basename(m['file'])[:5] + ".."
            self.canvas.create_text(px, py - 12, text=mesh_name, font=("Arial", 7), tags="mesh_marker")

    def draw_grid(self):
        self.canvas.delete("grid", "arena_border")
        
        px_min, py_min = self.m_to_px(-self.arena_w / 2, self.arena_h / 2)
        px_max, py_max = self.m_to_px(self.arena_w / 2, -self.arena_h / 2)
        
        self.canvas.create_rectangle(px_min, py_min, px_max, py_max, fill="#f9f9f9", outline="#3b82f6", width=2, tags="arena_border")
        
        start_x = math.ceil(-self.arena_w / 2)
        end_x = math.floor(self.arena_w / 2)
        for x in range(start_x, end_x + 1):
            px, _ = self.m_to_px(x, 0)
            color = "#a0a0a0" if x == 0 else "#e0e0e0"
            width = 2 if x == 0 else 1
            self.canvas.create_line(px, py_min, px, py_max, fill=color, width=width, tags="grid")

        start_y = math.ceil(-self.arena_h / 2)
        end_y = math.floor(self.arena_h / 2)
        for y in range(start_y, end_y + 1):
            _, py = self.m_to_px(0, y)
            color = "#a0a0a0" if y == 0 else "#e0e0e0"
            width = 2 if y == 0 else 1
            self.canvas.create_line(px_min, py, px_max, py, fill=color, width=width, tags="grid")

        self.canvas.tag_lower("grid")
        self.canvas.tag_lower("arena_border")

    def update_mesh_dropdown(self):
        files = [f for f in os.listdir(self.mesh_folder) if f.lower().endswith(('.dae', '.stl', '.obj'))]
        self.mesh_dropdown['values'] = files
        if files:
            self.mesh_dropdown.current(0)

    def px_to_m(self, px, py):
        cx, cy = self.canvas_size / 2.0, self.canvas_size / 2.0
        return (px - cx) / self.scale, -(py - cy) / self.scale

    def m_to_px(self, x, y):
        cx, cy = self.canvas_size / 2.0, self.canvas_size / 2.0
        return (x * self.scale) + cx, -(y * self.scale) + cy

    def load_mesh_folder(self):
        folder = filedialog.askdirectory(title="Selecione a pasta com os Meshes 3D")
        if folder:
            self.mesh_folder = folder
            self.update_mesh_dropdown()

    def get_snapped_endpoint(self, x1, y1, raw_x2, raw_y2):
        # 1. Prioridade Máxima: Snap na Parede (se ativado e encontrar)
        if self.snap_wall_var.get():
            snap_x, snap_y, did_snap = self.snap_to_walls(raw_x2, raw_y2)
            if did_snap:
                length = math.hypot(snap_x - x1, snap_y - y1)
                angle = math.atan2(snap_y - y1, snap_x - x1)
                return snap_x, snap_y, length, angle
                
        # 2. Prioridade Secundária: Snap de Ângulo
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
                # Calcula ponto inicial com chance de SNAP em paredes existentes
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
                    self.canvas.create_line(self.start_point[0], self.start_point[1], px2, py2, width=4, fill="black", tags="wall")
                
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
        
        # Desenha o marcador visual (quadrado magenta) se der Snap na parede
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
            self.canvas.create_line(self.start_point[0], self.start_point[1], px2, py2, width=4, fill="black", tags="wall")
            
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
        self.canvas.delete("wall", "preview", "mesh_marker", "snap_indicator")
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
      <!-- Deslocamos -0.5 no Z para que o topo da caixa de 1m fique no nível 0 -->
      <pose>0 0 -0.5 0 0 0</pose>
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