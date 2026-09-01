#!/usr/bin/env python3
import os
import math
import yaml
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = "cfg.yaml"

class WallBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Mundo Gazebo - Paredes e Meshes")
        
        self.scale = 20.0
        self.wall_height = 2.5 
        self.wall_thickness = 0.2

        self.start_point = None
        self.walls = []  
        self.placed_meshes = [] 
        self.mesh_folder = ""

        self.canvas_size = 700
        self.canvas = tk.Canvas(root, width=self.canvas_size, height=self.canvas_size, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.draw_grid()

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_move)

        panel = tk.Frame(root, width=250)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self.mode = tk.StringVar(value="wall")
        ttk.Radiobutton(panel, text="Modo: Desenhar Paredes", variable=self.mode, value="wall").pack(anchor="w", pady=5)
        ttk.Radiobutton(panel, text="Modo: Inserir Mesh", variable=self.mode, value="mesh").pack(anchor="w", pady=5)

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=10)

        self.lbl_length = tk.Label(panel, text="Tamanho da parede: 0.00 m", font=("Arial", 10, "bold"), fg="blue")
        self.lbl_length.pack(pady=5)

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=10)

        tk.Button(panel, text="Carregar Pasta de Meshes", command=self.load_mesh_folder).pack(fill=tk.X, pady=5)
        
        self.mesh_var = tk.StringVar()
        self.mesh_dropdown = ttk.Combobox(panel, textvariable=self.mesh_var, state="readonly")
        self.mesh_dropdown.pack(fill=tk.X, pady=5)
        
        tk.Label(panel, text="Rotação Yaw (graus):").pack(anchor="w")
        self.entry_yaw = tk.Entry(panel)
        self.entry_yaw.insert(0, "0.0")
        self.entry_yaw.pack(fill=tk.X, pady=5)
        
        tk.Label(panel, text="Altura Z (m):").pack(anchor="w")
        self.entry_z = tk.Entry(panel)
        self.entry_z.insert(0, "0.0")
        self.entry_z.pack(fill=tk.X, pady=5)

        ttk.Separator(panel, orient='horizontal').pack(fill='x', pady=15)

        tk.Button(panel, text="Limpar Tudo", command=self.clear_canvas, bg="#ffcccc").pack(fill=tk.X, pady=5)
        tk.Button(panel, text="Salvar Configs e Mundo", command=self.save_all, bg="#ccffcc", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=20)

        # Carrega as configurações (pasta e desenho anterior) ao iniciar
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    
                    # Restaura a pasta de meshes
                    saved_folder = config.get('mesh_folder', '')
                    if saved_folder and os.path.isdir(saved_folder):
                        self.mesh_folder = saved_folder
                        self.update_mesh_dropdown()
                    
                    # Restaura os desenhos no canvas
                    self.walls = config.get('walls', [])
                    self.placed_meshes = config.get('placed_meshes', [])
                    self.redraw_all()
            except Exception as e:
                print(f"Erro ao carregar config: {e}")

    def save_config(self):
        config = {
            'mesh_folder': self.mesh_folder,
            'walls': self.walls,
            'placed_meshes': self.placed_meshes
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(config, f)
        except Exception as e:
            print(f"Erro ao salvar config: {e}")

    def save_all(self):
        # 1. Cria a pasta results
        base_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(base_dir, "results")
        os.makedirs(results_dir, exist_ok=True)
        
        # 2. Salva o Mundo .SDF dentro de results/
        sdf_path = os.path.join(results_dir, "mundo_gerado.sdf")
        with open(sdf_path, "w") as f:
            f.write(self.generate_sdf())
            
        # 3. Salva o progresso e o caminho da pasta em cfg.yaml
        self.save_config()
        
        messagebox.showinfo("Sucesso", f"Progresso salvo no cfg.yaml!\n\nMundo exportado em:\n{sdf_path}")

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

    def update_mesh_dropdown(self):
        files = [f for f in os.listdir(self.mesh_folder) if f.lower().endswith(('.dae', '.stl', '.obj'))]
        self.mesh_dropdown['values'] = files
        if files:
            self.mesh_dropdown.current(0)

    def draw_grid(self):
        step = int(self.scale)
        for i in range(0, self.canvas_size, step):
            color = "#d0d0d0" if i % (step * 5) == 0 else "#f0f0f0"
            self.canvas.create_line(i, 0, i, self.canvas_size, fill=color, tags="grid")
            self.canvas.create_line(0, i, self.canvas_size, i, fill=color, tags="grid")

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

    def on_click(self, event):
        if self.mode.get() == "wall":
            if self.start_point is None:
                self.start_point = (event.x, event.y)
            else:
                x1, y1 = self.px_to_m(self.start_point[0], self.start_point[1])
                x2, y2 = self.px_to_m(event.x, event.y)
                
                if math.hypot(x2 - x1, y2 - y1) > 0.05:
                    self.walls.append((x1, y1, x2, y2))
                    self.canvas.create_line(self.start_point[0], self.start_point[1], event.x, event.y, width=4, fill="black", tags="wall")
                
                self.start_point = None
                self.canvas.delete("preview")
                self.lbl_length.config(text="Tamanho da parede: 0.00 m")
        
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
            
            self.placed_meshes.append({'file': abs_path, 'x': x, 'y': y, 'z': z, 'yaw': yaw})
            
            r = 6
            self.canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r, fill="orange", tags="mesh_marker")
            self.canvas.create_text(event.x, event.y - 12, text=mesh_file[:5]+"..", font=("Arial", 7), tags="mesh_marker")

    def on_move(self, event):
        if self.mode.get() == "wall" and self.start_point:
            self.canvas.delete("preview")
            
            x1, y1 = self.px_to_m(self.start_point[0], self.start_point[1])
            x2, y2 = self.px_to_m(event.x, event.y)
            length = math.hypot(x2 - x1, y2 - y1)
            
            self.lbl_length.config(text=f"Tamanho da parede: {length:.2f} m")
            self.canvas.create_line(self.start_point[0], self.start_point[1], event.x, event.y, width=2, dash=(4, 4), fill="red", tags="preview")

    def clear_canvas(self):
        self.walls.clear()
        self.placed_meshes.clear()
        self.start_point = None
        self.canvas.delete("wall", "preview", "mesh_marker")
        self.lbl_length.config(text="Tamanho da parede: 0.00 m")

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
      <link name="link">
        <collision name="collision"><geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry></collision>
        <visual name="visual"><geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry><material><ambient>0 0 0 1</ambient></material></visual>
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