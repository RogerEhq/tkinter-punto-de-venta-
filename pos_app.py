import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
# Importaciones para Estilos
from ttkbootstrap import Style
from ttkbootstrap.constants import *
# Importaciones para Exportación
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Punto de Venta (POS) - Tienda")

        # 1. Configuración de Estilo y Tema (ttkbootstrap)
        # --- CAMBIO DE ESTILO: De 'superhero' (oscuro) a 'litera' (claro) ---
        self.style = Style(theme='litera')
        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        # 2. Inicializar la Base de Datos
        self.conn = sqlite3.connect('pos_data.db')
        self.cursor = self.conn.cursor()
        self.setup_database()

        # 3. Variables de la Aplicación
        self.caja_abierta = False
        self.productos_carrito = {}
        self.ganancia_caja_actual = 0.0

        # 4. Crear la Interfaz de Usuario
        self.create_widgets()

        # 5. Cargar productos al iniciar
        self.cargar_productos()

        # 6. Intentar recuperar estado de caja
        self.check_caja_status()

    # ====================================================================
    #           SECCIÓN DE BASE DE DATOS (SQLite) - SIN CAMBIOS
    # ====================================================================

    def setup_database(self):
        # Tabla de Productos
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                categoria TEXT,
                descripcion TEXT,
                stock INTEGER NOT NULL,
                precio REAL NOT NULL
            )
        ''')

        # Tabla de Ventas
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                total REAL NOT NULL,
                detalles TEXT NOT NULL
            )
        ''')

        # Tabla de Control de Caja
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS caja (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estado TEXT NOT NULL,
                fecha_apertura TEXT NOT NULL,
                fecha_cierre TEXT,
                ganancia_total REAL
            )
        ''')
        self.conn.commit()

    # ====================================================================
    #           SECCIÓN DE WIDGETS Y GUI - AJUSTES ESTÉTICOS
    # ====================================================================

    def create_widgets(self):
        # Contenedor principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Paneles principales
        # Ajustamos a 'primary' para que los LabelFrame se vean bien en tema claro
        panel_productos = ttk.LabelFrame(main_frame, text="Gestión de Productos", padding="10", bootstyle="primary")
        panel_productos.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        panel_ventas = ttk.LabelFrame(main_frame, text="Punto de Venta (Caja)", padding="10", bootstyle="primary")
        panel_ventas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        panel_registros = ttk.LabelFrame(main_frame, text="Registros de Ventas y Caja", padding="10",
                                         bootstyle="primary")
        panel_registros.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        # Configurar expansión de columnas
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=3)
        main_frame.grid_rowconfigure(1, weight=1)

        # Crear widgets de cada sección
        self.create_producto_widgets(panel_productos)
        self.create_venta_widgets(panel_ventas)
        self.create_registros_widgets(panel_registros)

    # --------------------------------------------------------------------
    #                           Gestión de Productos
    # --------------------------------------------------------------------

    def create_producto_widgets(self, frame):
        # Entrada de Búsqueda
        ttk.Label(frame, text="Buscar Producto (ID, Nombre, Categoría):", bootstyle="primary").grid(row=0, column=0,
                                                                                                    pady=5, sticky='w')
        # Cambiamos a 'default' o 'info' para contraste en tema claro
        self.search_entry = ttk.Entry(frame, width=30, bootstyle="info")
        self.search_entry.grid(row=0, column=1, pady=5, padx=5, sticky='ew')
        self.search_entry.bind('<KeyRelease>', self.buscar_producto)

        # Treeview de Productos
        columns = ("ID", "Nombre", "Categoría", "Stock", "Precio")
        self.productos_tree = ttk.Treeview(frame, columns=columns, show='headings', height=10, bootstyle="default")
        for col in columns:
            self.productos_tree.heading(col, text=col)
            self.productos_tree.column(col, width=100, anchor='center')
        self.productos_tree.column("ID", width=40)
        self.productos_tree.column("Nombre", width=150)
        self.productos_tree.grid(row=1, column=0, columnspan=3, pady=10, sticky='nsew')

        # Scrollbar para el Treeview
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.productos_tree.yview, bootstyle="primary")
        vsb.grid(row=1, column=3, sticky='ns')
        self.productos_tree.configure(yscrollcommand=vsb.set)

        # Frame de Botones de Producto
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)

        ttk.Button(btn_frame, text="➕ Agregar Producto", command=self.open_agregar_producto, bootstyle="success").pack(
            side='left', padx=10)
        ttk.Button(btn_frame, text="✏️ Editar Producto", command=self.open_editar_producto, bootstyle="warning").pack(
            side='left', padx=10)
        ttk.Button(btn_frame, text="🗑️ Eliminar Producto", command=self.eliminar_producto, bootstyle="danger").pack(
            side='left', padx=10)

        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(1, weight=1)

    # --------------------------------------------------------------------
    #                           Punto de Venta (Caja)
    # --------------------------------------------------------------------

    def create_venta_widgets(self, frame):
        # Control de Caja (Apertura/Cierre)
        caja_frame = ttk.LabelFrame(frame, text="Control de Caja", padding=10, bootstyle="secondary")
        caja_frame.pack(fill='x', pady=5)
        # Aseguramos un buen contraste para el estado de caja
        self.caja_status_label = ttk.Label(caja_frame, text="Caja Cerrada", bootstyle="danger",
                                           font=("Segoe UI", 14, "bold"))
        self.caja_status_label.pack(side='left', padx=10)
        self.caja_button = ttk.Button(caja_frame, text="Abrir Caja", command=self.toggle_caja, bootstyle="success")
        self.caja_button.pack(side='right')

        # Selección de Producto para Venta
        ttk.Label(frame, text="Buscar Producto para Venta (ID/Nombre):", bootstyle="info").pack(fill='x', pady=5)
        self.venta_search_entry = ttk.Entry(frame, bootstyle="secondary")
        self.venta_search_entry.pack(fill='x', pady=5)

        add_frame = ttk.Frame(frame)
        add_frame.pack(fill='x', pady=5)
        ttk.Label(add_frame, text="Cantidad:", font=("Segoe UI", 11, "bold")).pack(side='left')
        self.cantidad_entry = ttk.Entry(add_frame, width=5)
        self.cantidad_entry.pack(side='left', padx=5)
        ttk.Button(add_frame, text="🛒 Añadir al Carrito", command=self.add_to_carrito, bootstyle="primary").pack(
            side='right', fill='x', expand=True)

        # Treeview del Carrito
        self.carrito_tree = ttk.Treeview(frame, columns=("Nombre", "Cantidad", "Precio Unitario", "Subtotal"),
                                         show='headings', height=8, bootstyle="default")
        self.carrito_tree.heading("Nombre", text="Producto")
        self.carrito_tree.heading("Cantidad", text="Cant.")
        self.carrito_tree.heading("Precio Unitario", text="P. Unit.")
        self.carrito_tree.heading("Subtotal", text="Subtotal")
        self.carrito_tree.column("Cantidad", width=50, anchor='center')
        self.carrito_tree.column("Precio Unitario", width=80, anchor='e')
        self.carrito_tree.column("Subtotal", width=80, anchor='e')
        self.carrito_tree.pack(fill='both', expand=True, pady=10)

        # Total de la Venta
        total_frame = ttk.Frame(frame, padding=5, relief=tk.RIDGE,
                                bootstyle="info")  # Cambio de inverse-primary a info para tema claro
        total_frame.pack(fill='x', pady=10)
        ttk.Label(total_frame, text="TOTAL A PAGAR:", font=("Segoe UI", 16, "bold"), bootstyle="inverse-info").pack(
            side='left', padx=5)

        self.total_label = ttk.Label(total_frame, text="$0.00", font=("Segoe UI", 20, "bold"), bootstyle="primary")
        self.total_label.pack(side='right', padx=5)

        # Botón de Finalizar Venta
        ttk.Button(frame, text="💰 Finalizar Venta", command=self.finalizar_venta, bootstyle="success", padding=10).pack(
            fill='x',
            pady=5)
        ttk.Button(frame, text="❌ Vaciar Carrito", command=self.vaciar_carrito, bootstyle="warning").pack(fill='x')

    # --------------------------------------------------------------------
    #                           Registros y Ventas
    # --------------------------------------------------------------------

    def create_registros_widgets(self, frame):
        # Cambiamos a 'primary' para que las pestañas se vean bien en tema claro
        notebook = ttk.Notebook(frame, bootstyle="primary")
        notebook.pack(expand=True, fill="both")

        # Pestaña de Ventas
        ventas_frame = ttk.Frame(notebook, padding=5)
        notebook.add(ventas_frame, text="Historial de Ventas")

        # Treeview de Ventas
        columns_ventas = ("ID Venta", "Fecha", "Total", "Detalles")
        self.ventas_tree = ttk.Treeview(ventas_frame, columns=columns_ventas, show='headings', height=5,
                                        bootstyle="default")
        for col in columns_ventas:
            self.ventas_tree.heading(col, text=col)
            self.ventas_tree.column(col, width=150, anchor='center')
        self.ventas_tree.pack(fill='both', expand=True, pady=(0, 5))

        # Frame de Botones de Exportación
        export_btn_frame = ttk.Frame(ventas_frame)
        export_btn_frame.pack(fill='x', pady=5)

        # --- NUEVOS BOTONES DE EXPORTACIÓN ---
        ttk.Button(export_btn_frame, text="📄 Exportar a PDF", command=self.exportar_a_pdf, bootstyle="info").pack(
            side='left', padx=5, fill='x', expand=True)
        ttk.Button(export_btn_frame, text="📊 Exportar a Excel", command=self.exportar_a_excel,
                   bootstyle="success").pack(side='left', padx=5, fill='x', expand=True)

        # Pestaña de Caja y Ganancias
        caja_frame = ttk.Frame(notebook, padding=5)
        notebook.add(caja_frame, text="Registro de Cajas")

        columns_caja = ("ID Caja", "Estado", "Apertura", "Cierre", "Ganancia")
        self.caja_tree = ttk.Treeview(caja_frame, columns=columns_caja, show='headings', height=5, bootstyle="default")
        for col in columns_caja:
            self.caja_tree.heading(col, text=col)
            self.caja_tree.column(col, width=120, anchor='center')
        self.caja_tree.pack(fill='both', expand=True)

        # Cargar registros al iniciar
        self.cargar_registros_ventas()
        self.cargar_registros_caja()

    def cargar_productos(self, busqueda=""):
        for item in self.productos_tree.get_children():
            self.productos_tree.delete(item)

        query = "SELECT id, nombre, categoria, stock, precio FROM productos"
        if busqueda:
            query += f" WHERE nombre LIKE '%{busqueda}%' OR categoria LIKE '%{busqueda}%' OR id LIKE '{busqueda}%'"

        self.cursor.execute(query)
        productos = self.cursor.fetchall()

        for prod in productos:
            tag = 'low_stock' if prod[3] < 5 else ''
            stock_str = f"⚠️ {prod[3]}" if prod[3] < 5 else prod[3]
            self.productos_tree.insert("", "end", values=(prod[0], prod[1], prod[2], stock_str, f"${prod[4]:.2f}"),
                                       tags=(tag,))

        self.productos_tree.tag_configure('low_stock', foreground='red', font=("Segoe UI", 10, "bold"))

    def buscar_producto(self, event):
        busqueda = self.search_entry.get()
        self.cargar_productos(busqueda)

    def open_agregar_producto(self):
        self.create_producto_form_window("Agregar")

    def open_editar_producto(self):
        selected_item = self.productos_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "Selecciona un producto para editar.")
            return

        producto_id = self.productos_tree.item(selected_item, 'values')[0]

        self.cursor.execute("SELECT * FROM productos WHERE id=?", (producto_id,))
        producto = self.cursor.fetchone()

        if producto:
            self.create_producto_form_window("Editar", producto)
        else:
            messagebox.showerror("Error", "Producto no encontrado en la base de datos.")

    def create_producto_form_window(self, mode, producto=None):
        top = tk.Toplevel(self.root)
        top.title(f"{mode} Producto")
        top.grab_set()

        frame = ttk.Frame(top, padding=10)
        frame.pack(padx=10, pady=10)

        fields = ["Nombre", "Categoría", "Descripción", "Stock", "Precio"]
        entries = {}

        for i, field in enumerate(fields):
            ttk.Label(frame, text=f"{field}:", bootstyle="info").grid(row=i, column=0, pady=5, sticky='w')
            entry = ttk.Entry(frame, width=40, bootstyle="secondary")
            entry.grid(row=i, column=1, pady=5, padx=5, sticky='ew')
            entries[field] = entry

        if mode == "Editar" and producto:
            entries["Nombre"].insert(0, producto[1])
            entries["Categoría"].insert(0, producto[2])
            entries["Descripción"].insert(0, producto[3])
            entries["Stock"].insert(0, str(producto[4]))
            entries["Precio"].insert(0, str(producto[5]))

            action_command = lambda: self.guardar_producto(mode, top, entries, producto[0])
        else:
            action_command = lambda: self.guardar_producto(mode, top, entries)

        ttk.Button(frame, text=mode, command=action_command, bootstyle="success", padding=5).grid(row=len(fields),
                                                                                                  column=0,
                                                                                                  columnspan=2, pady=10)

        top.grid_columnconfigure(0, weight=1)

    def guardar_producto(self, mode, top_window, entries, producto_id=None):
        try:
            nombre = entries["Nombre"].get()
            categoria = entries["Categoría"].get()
            descripcion = entries["Descripción"].get()
            stock = int(entries["Stock"].get())
            precio = float(entries["Precio"].get())

            if not nombre or stock < 0 or precio <= 0:
                raise ValueError("Campos obligatorios incompletos o valores inválidos (Stock/Precio).")

            if mode == "Agregar":
                self.cursor.execute(
                    "INSERT INTO productos (nombre, categoria, descripcion, stock, precio) VALUES (?, ?, ?, ?, ?)",
                    (nombre, categoria, descripcion, stock, precio))
                messagebox.showinfo("Éxito", "Producto agregado correctamente.")
            elif mode == "Editar":
                self.cursor.execute(
                    "UPDATE productos SET nombre=?, categoria=?, descripcion=?, stock=?, precio=? WHERE id=?",
                    (nombre, categoria, descripcion, stock, precio, producto_id))
                messagebox.showinfo("Éxito", "Producto editado correctamente.")

            self.conn.commit()
            self.cargar_productos()
            top_window.destroy()

        except ValueError as e:
            messagebox.showerror("Error de Validación", str(e))
        except Exception as e:
            messagebox.showerror("Error de BD", f"Ocurrió un error al guardar: {e}")

    def eliminar_producto(self):
        selected_item = self.productos_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "Selecciona un producto para eliminar.")
            return

        producto_id = self.productos_tree.item(selected_item, 'values')[0]
        nombre = self.productos_tree.item(selected_item, 'values')[1]

        if messagebox.askyesno("Confirmar Eliminación",
                               f"¿Estás seguro de eliminar el producto '{nombre}' (ID: {producto_id})?"):
            try:
                self.cursor.execute("DELETE FROM productos WHERE id=?", (producto_id,))
                self.conn.commit()
                messagebox.showinfo("Éxito", "Producto eliminado correctamente.")
                self.cargar_productos()
            except Exception as e:
                messagebox.showerror("Error de BD", f"Ocurrió un error al eliminar: {e}")

    def check_caja_status(self):
        self.cursor.execute("SELECT id, ganancia_total FROM caja WHERE estado='Abierta' ORDER BY id DESC LIMIT 1")
        last_caja = self.cursor.fetchone()

        if last_caja:
            self.caja_abierta = True
            self.current_caja_id = last_caja[0]
            self.ganancia_caja_actual = last_caja[1]
            self.update_caja_gui()
            messagebox.showinfo("Caja Recuperada", "Se encontró una caja abierta previamente. Reanudando operaciones.")
        else:
            self.caja_abierta = False
            self.current_caja_id = None
            self.ganancia_caja_actual = 0.0
            self.update_caja_gui()

    def toggle_caja(self):
        if self.caja_abierta:
            if not messagebox.askyesno("Cerrar Caja",
                                       f"¿Deseas cerrar la caja? Ganancia total actual: ${self.ganancia_caja_actual:.2f}"):
                return

            fecha_cierre = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("UPDATE caja SET estado='Cerrada', fecha_cierre=?, ganancia_total=? WHERE id=?",
                                (fecha_cierre, self.ganancia_caja_actual, self.current_caja_id))
            self.conn.commit()

            self.caja_abierta = False
            self.ganancia_caja_actual = 0.0
            messagebox.showinfo("Caja Cerrada",
                                f"Caja cerrada exitosamente. Ganancia registrada: ${self.ganancia_caja_actual:.2f}")
            self.cargar_registros_caja()

        else:
            fecha_apertura = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT INTO caja (estado, fecha_apertura, ganancia_total) VALUES (?, ?, ?)",
                                ('Abierta', fecha_apertura, 0.0))
            self.conn.commit()
            self.current_caja_id = self.cursor.lastrowid
            self.caja_abierta = True
            messagebox.showinfo("Caja Abierta", "Caja abierta. Puedes empezar a vender.")

        self.update_caja_gui()
        self.vaciar_carrito()

    def update_caja_gui(self):
        if self.caja_abierta:
            self.caja_status_label.config(text=f"CAJA ABIERTA | Ganancia: ${self.ganancia_caja_actual:.2f}",
                                          bootstyle="success")
            self.caja_button.config(text="Cerrar Caja", bootstyle="danger")
        else:
            self.caja_status_label.config(text="CAJA CERRADA", bootstyle="danger")
            self.caja_button.config(text="Abrir Caja", bootstyle="success")

    def add_to_carrito(self):
        if not self.caja_abierta:
            messagebox.showerror("Error", "Debes abrir caja para realizar ventas.")
            return

        search_term = self.venta_search_entry.get().strip()
        cantidad_str = self.cantidad_entry.get().strip()

        if not search_term or not cantidad_str:
            messagebox.showerror("Error", "Ingresa un producto (ID/Nombre) y la cantidad.")
            return

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "La cantidad debe ser un número entero positivo.")
            return

        query = "SELECT id, nombre, stock, precio FROM productos WHERE id=? OR nombre LIKE ?"
        self.cursor.execute(query, (search_term, f'%{search_term}%'))
        productos = self.cursor.fetchall()

        if not productos:
            messagebox.showerror("Error", "Producto no encontrado.")
            return

        producto = productos[0]
        prod_id, nombre, stock_actual, precio = producto

        if cantidad > stock_actual:
            messagebox.showwarning("Stock Insuficiente", f"Solo hay {stock_actual} unidades de '{nombre}' en stock.")
            return

        if prod_id in self.productos_carrito:
            self.productos_carrito[prod_id]['cantidad'] += cantidad
        else:
            self.productos_carrito[prod_id] = {
                'nombre': nombre,
                'precio': precio,
                'cantidad': cantidad
            }

        self.venta_search_entry.delete(0, tk.END)
        self.cantidad_entry.delete(0, tk.END)

        self.update_carrito_gui()

    def update_carrito_gui(self):
        for item in self.carrito_tree.get_children():
            self.carrito_tree.delete(item)

        total_venta = 0.0

        for prod_id, data in self.productos_carrito.items():
            subtotal = data['precio'] * data['cantidad']
            total_venta += subtotal

            self.carrito_tree.insert("", "end", values=(
                data['nombre'],
                data['cantidad'],
                f"${data['precio']:.2f}",
                f"${subtotal:.2f}"
            ), tags=(prod_id,))

        self.total_label.config(text=f"${total_venta:.2f}")

    def vaciar_carrito(self):
        if self.productos_carrito:
            if messagebox.askyesno("Confirmar", "¿Deseas vaciar el carrito actual?"):
                self.productos_carrito = {}
                self.update_carrito_gui()

    def finalizar_venta(self):
        if not self.caja_abierta:
            messagebox.showerror("Error", "Debes abrir caja para realizar ventas.")
            return

        if not self.productos_carrito:
            messagebox.showerror("Error", "El carrito está vacío.")
            return

        total_venta = float(self.total_label.cget("text").replace('$', ''))
        fecha_venta = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        detalles_venta = []
        ganancia_bruta = 0.0

        for prod_id, data in self.productos_carrito.items():
            cantidad = data['cantidad']
            precio = data['precio']
            nombre = data['nombre']

            self.cursor.execute("UPDATE productos SET stock = stock - ? WHERE id=?", (cantidad, prod_id))

            detalles_venta.append(f"{nombre} ({cantidad} x ${precio:.2f})")

            ganancia_bruta += (precio * cantidad)

        detalles_str = " | ".join(detalles_venta)
        self.cursor.execute("INSERT INTO ventas (fecha, total, detalles) VALUES (?, ?, ?)",
                            (fecha_venta, total_venta, detalles_str))

        self.ganancia_caja_actual += ganancia_bruta
        self.cursor.execute("UPDATE caja SET ganancia_total=? WHERE id=?",
                            (self.ganancia_caja_actual, self.current_caja_id))

        self.conn.commit()

        messagebox.showinfo("Venta Exitosa", f"Venta registrada por ${total_venta:.2f}")
        self.productos_carrito = {}
        self.update_carrito_gui()
        self.cargar_productos()
        self.cargar_registros_ventas()
        self.update_caja_gui()

    # ====================================================================
    #           SECCIÓN DE REGISTROS Y EXPORTACIÓN - SIN CAMBIOS DE LÓGICA
    # ====================================================================

    def obtener_datos_ventas(self):
        """Consulta la base de datos y retorna los datos de ventas como una lista de tuplas."""
        self.cursor.execute("SELECT id, fecha, total, detalles FROM ventas ORDER BY id DESC")
        return self.cursor.fetchall()

    def cargar_registros_ventas(self):
        for item in self.ventas_tree.get_children():
            self.ventas_tree.delete(item)

        ventas = self.obtener_datos_ventas()

        for venta in ventas:
            self.ventas_tree.insert("", "end", values=(venta[0], venta[1].split(' ')[0], f"${venta[2]:.2f}", venta[3]))

    def exportar_a_excel(self):
        try:
            # 1. Obtener datos crudos de la BD
            data = self.obtener_datos_ventas()
            if not data:
                messagebox.showwarning("Advertencia", "No hay registros de ventas para exportar.")
                return

            # 2. Definir columnas
            columnas = ["ID Venta", "Fecha", "Total", "Detalles de Venta"]

            # 3. Crear DataFrame de Pandas
            df = pd.DataFrame(data, columns=columnas)

            # 4. Diálogo para guardar el archivo
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Archivos Excel", "*.xlsx")],
                title="Guardar Registro de Ventas (Excel)"
            )

            if filepath:
                # 5. Exportar a Excel (usa openpyxl por defecto)
                df.to_excel(filepath, index=False)
                messagebox.showinfo("Éxito", f"Datos exportados a Excel:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"Ocurrió un error al exportar a Excel: {e}")

    def exportar_a_pdf(self):
        try:
            # 1. Obtener datos
            data = self.obtener_datos_ventas()
            if not data:
                messagebox.showwarning("Advertencia", "No hay registros de ventas para exportar.")
                return

            # 2. Diálogo para guardar el archivo
            filepath = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                title="Guardar Registro de Ventas (PDF)"
            )

            if not filepath:
                return

            # 3. Preparar PDF con ReportLab
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            styles = getSampleStyleSheet()
            elementos = []

            # Título
            elementos.append(Paragraph("REPORTE DE HISTORIAL DE VENTAS", styles['h1']))
            elementos.append(Paragraph(f"Fecha de Reporte: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                       styles['Normal']))
            elementos.append(Paragraph("<br/>", styles['Normal']))

            # Preparar datos para la tabla PDF
            header = ["ID Venta", "Fecha", "Total", "Detalles"]
            table_data = [header]

            total_ventas = 0.0

            for row in data:
                # Asegurar el formato de moneda y sumar el total
                total_str = f"${row[2]:.2f}"
                total_ventas += row[2]

                # ReportLab maneja listas de listas para la tabla
                table_data.append([row[0], row[1].split(' ')[0], total_str, row[3]])

                # Crear la tabla
            table = Table(table_data, colWidths=[50, 80, 70, 340])  # Ancho fijo para columnas

            # Estilo de la tabla
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),  # Alinear Total a la derecha
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ])
            table.setStyle(style)
            elementos.append(table)

            # Total General
            elementos.append(Paragraph("<br/>", styles['Normal']))
            elementos.append(
                Paragraph(f"TOTAL DE VENTAS REGISTRADAS: <font color='red'>${total_ventas:.2f}</font>", styles['h3']))

            # 4. Construir y guardar PDF
            doc.build(elementos)
            messagebox.showinfo("Éxito", f"Datos exportados a PDF:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error de Exportación",
                                 f"Ocurrió un error al exportar a PDF. Asegúrate de tener permisos de escritura. Error: {e}")

    def cargar_registros_caja(self):
        for item in self.caja_tree.get_children():
            self.caja_tree.delete(item)

        self.cursor.execute(
            "SELECT id, estado, fecha_apertura, fecha_cierre, ganancia_total FROM caja ORDER BY id DESC")
        cajas = self.cursor.fetchall()

        for caja in cajas:
            fecha_cierre_disp = caja[3].split(' ')[0] if caja[3] else "N/A"
            self.caja_tree.insert("", "end", values=(
                caja[0],
                caja[1],
                caja[2].split(' ')[0],
                fecha_cierre_disp,
                f"${caja[4]:.2f}"
            ), tags=caja[1])

            # Los colores se mantienen para el contraste del estado de la caja.
            if caja[1] == 'Abierta':
                self.caja_tree.tag_configure("Abierta", background='#198754', foreground='white')
            elif caja[1] == 'Cerrada':
                self.caja_tree.tag_configure("Cerrada", background='#dc3545', foreground='white')


# ====================================================================
#           EJECUCIÓN PRINCIPAL
# ====================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()