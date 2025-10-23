import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime

# --- Importaciones para Estilos (ttkbootstrap) ---
try:
    from ttkbootstrap import Style
    from ttkbootstrap.constants import *
except ImportError:
    messagebox.showerror("Error Fatal", "Falta 'ttkbootstrap'. Ejecuta 'pip install ttkbootstrap'")
    exit()

# --- Importaciones para Exportación (pandas, reportlab) ---
try:
    import pandas as pd
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    print("ADVERTENCIA: Las funciones de exportación (Excel/PDF) no estarán disponibles sin 'pandas' y 'reportlab'.")


# ------------------------------------------

# ====================================================================
#           CLASE DE RECEPCIÓN DE MERCANCÍA (AUMENTO DE STOCK)
# ====================================================================

class RecepcionMercanciaWindow:
    def __init__(self, master, conn, refresh_callback):
        self.master = master
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.refresh_callback = refresh_callback  # Para actualizar el Treeview principal

        top = tk.Toplevel(master)
        top.title("📦 Recepción de Mercancía (Aumentar Stock)")
        top.grab_set()

        self.frame = ttk.Frame(top, padding=20)
        self.frame.pack(expand=True, fill='both')

        self.producto_id = None
        self.create_widgets(self.frame)

    def create_widgets(self, frame):
        # Búsqueda
        ttk.Label(frame, text="ID o Nombre del Producto:", bootstyle="info").grid(row=0, column=0, padx=5, pady=5,
                                                                                  sticky='w')
        self.search_entry = ttk.Entry(frame, width=20, bootstyle="secondary")
        self.search_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(frame, text="🔍 Buscar", command=self.buscar_producto, bootstyle="primary").grid(row=0, column=2,
                                                                                                   padx=5, pady=5)

        # Información del Producto
        info_frame = ttk.LabelFrame(frame, text="Producto Seleccionado", padding=10, bootstyle="info")
        info_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=10, sticky='ew')

        self.nombre_label = ttk.Label(info_frame, text="Nombre: N/A", font=("Segoe UI", 11))
        self.nombre_label.pack(anchor='w')
        self.stock_label = ttk.Label(info_frame, text="Stock Actual: N/A", font=("Segoe UI", 11, "bold"))
        self.stock_label.pack(anchor='w')

        # Aumento de Stock
        ttk.Label(frame, text="Cantidad a Agregar:", bootstyle="success").grid(row=2, column=0, padx=5, pady=10,
                                                                               sticky='w')
        self.cantidad_entry = ttk.Entry(frame, width=10, bootstyle="secondary")
        self.cantidad_entry.grid(row=2, column=1, padx=5, pady=10, sticky='ew')

        self.btn_recibir = ttk.Button(frame, text="➕ Aumentar Stock", command=self.aumentar_stock, bootstyle="success",
                                      state=DISABLED)
        self.btn_recibir.grid(row=3, column=0, columnspan=3, pady=10, sticky='ew')

        frame.grid_columnconfigure(1, weight=1)

    def buscar_producto(self):
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("Advertencia", "Ingresa un ID o nombre para buscar.")
            return

        query = "SELECT id, nombre, stock FROM productos WHERE id=? OR nombre LIKE ?"
        self.cursor.execute(query, (search_term, f'%{search_term}%'))
        producto = self.cursor.fetchone()

        if producto:
            self.producto_id = producto[0]
            nombre = producto[1]
            stock = producto[2]

            self.nombre_label.config(text=f"Nombre: {nombre}")
            self.stock_label.config(text=f"Stock Actual: {stock}")
            self.btn_recibir.config(state=NORMAL)
        else:
            self.producto_id = None
            self.nombre_label.config(text="Nombre: Producto no encontrado")
            self.stock_label.config(text="Stock Actual: N/A")
            self.btn_recibir.config(state=DISABLED)
            messagebox.showerror("Error", "Producto no encontrado en la base de datos.")

    def aumentar_stock(self):
        if not self.producto_id:
            messagebox.showwarning("Advertencia", "Primero busca y selecciona un producto.")
            return

        try:
            cantidad = int(self.cantidad_entry.get())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "La cantidad debe ser un número entero positivo.")
            return

        try:
            # Actualiza el stock sumando la cantidad recibida
            self.cursor.execute("UPDATE productos SET stock = stock + ? WHERE id=?", (cantidad, self.producto_id))
            self.conn.commit()

            # Recarga la información de la ventana local y la principal
            self.buscar_producto()
            self.refresh_callback()

            messagebox.showinfo("Éxito",
                                f"Stock aumentado en {cantidad} unidades para el producto ID {self.producto_id}.")
            self.cantidad_entry.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror("Error de BD", f"Ocurrió un error al actualizar el stock: {e}")


# ====================================================================
#           CLASE PRINCIPAL DE LA APLICACIÓN POS
# ====================================================================

class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Punto de Venta (POS) - Tienda")

        # 1. Configuración de Estilo y Tema
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
        self.current_caja_id = None

        # 4. Crear la Interfaz de Usuario
        self.create_widgets()

        # 5. Cargar productos y registros
        self.cargar_productos()
        self.cargar_registros_ventas()
        self.cargar_registros_caja()

        # 6. Intentar recuperar estado de caja
        self.check_caja_status()

    # ====================================================================
    #           SECCIÓN DE BASE DE DATOS (SQLite)
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

        # Tabla de Ventas (Se añade columna para marcar si es una devolución)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                total REAL NOT NULL,
                detalles TEXT NOT NULL,
                es_devolucion INTEGER DEFAULT 0
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
    #           SECCIÓN DE WIDGETS Y GUI
    # ====================================================================

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Paneles principales
        panel_productos = ttk.LabelFrame(main_frame, text="Gestión de Inventario", padding="10", bootstyle="primary")
        panel_productos.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        panel_ventas = ttk.LabelFrame(main_frame, text="Punto de Venta (Caja)", padding="10", bootstyle="primary")
        panel_ventas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        panel_registros = ttk.LabelFrame(main_frame, text="Registros de Ventas y Caja", padding="10",
                                         bootstyle="primary")
        panel_registros.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=3)
        main_frame.grid_rowconfigure(1, weight=1)

        self.create_producto_widgets(panel_productos)
        self.create_venta_widgets(panel_ventas)
        self.create_registros_widgets(panel_registros)

    def create_producto_widgets(self, frame):
        # Frame de Búsqueda y Recepción
        top_frame = ttk.Frame(frame)
        top_frame.grid(row=0, column=0, columnspan=3, sticky='ew')

        ttk.Label(top_frame, text="Buscar Producto (ID/Nombre):", bootstyle="primary").pack(side='left', pady=5, padx=5)
        self.search_entry = ttk.Entry(top_frame, width=20, bootstyle="info")
        self.search_entry.pack(side='left', pady=5, padx=5, fill='x', expand=True)
        self.search_entry.bind('<KeyRelease>', self.buscar_producto)

        # --- NUEVO BOTÓN PARA RECEPCIÓN DE MERCANCÍA ---
        ttk.Button(top_frame, text="📦 Recibir Mercancía", command=self.open_recepcion_mercancia, bootstyle="info").pack(
            side='right', padx=5)

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

        # Frame de Botones de Producto (CRUD)
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

    def create_venta_widgets(self, frame):
        # ... (Widgets de venta, carrito y total, sin cambios) ...
        # Control de Caja (Apertura/Cierre)
        caja_frame = ttk.LabelFrame(frame, text="Control de Caja", padding=10, bootstyle="secondary")
        caja_frame.pack(fill='x', pady=5)
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
                                bootstyle="info")
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

    def create_registros_widgets(self, frame):
        notebook = ttk.Notebook(frame, bootstyle="primary")
        notebook.pack(expand=True, fill="both")

        # Pestaña de Ventas
        ventas_frame = ttk.Frame(notebook, padding=5)
        notebook.add(ventas_frame, text="Historial de Ventas")

        # Treeview de Ventas
        # Columnas actualizadas para mostrar el estado
        columns_ventas = ("ID Venta", "Fecha", "Total", "Detalles", "Estado")
        self.ventas_tree = ttk.Treeview(ventas_frame, columns=columns_ventas, show='headings', height=5,
                                        bootstyle="default")
        for col in columns_ventas:
            self.ventas_tree.heading(col, text=col)
            self.ventas_tree.column(col, width=100, anchor='center')
        self.ventas_tree.column("Detalles", width=250)
        self.ventas_tree.column("Estado", width=70)
        self.ventas_tree.pack(fill='both', expand=True, pady=(0, 5))

        # --- NUEVO BOTÓN DE DEVOLUCIÓN ---
        btn_devolucion = ttk.Button(ventas_frame, text="↩️ Realizar Devolución de Venta",
                                    command=self.realizar_devolucion, bootstyle="danger")
        btn_devolucion.pack(pady=5)

        # Frame de Botones de Exportación
        export_btn_frame = ttk.Frame(ventas_frame)
        export_btn_frame.pack(fill='x', pady=5)

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

    # ====================================================================
    #           MÉTODOS DE INVENTARIO Y DEVOLUCIÓN (Nuevos/Modificados)
    # ====================================================================

    def open_recepcion_mercancia(self):
        """Abre la ventana para aumentar el stock de productos."""
        RecepcionMercanciaWindow(self.root, self.conn, self.cargar_productos)

    # --- Devolución de Venta ---

    def realizar_devolucion(self):
        selected_item = self.ventas_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "Selecciona una venta del historial para realizar la devolución.")
            return

        # Obtenemos los valores del Treeview
        venta_id, _, total, detalles, estado = self.ventas_tree.item(selected_item, 'values')
        venta_id = int(venta_id)

        if estado == "DEVOLUCIÓN":
            messagebox.showwarning("Advertencia", "Esta venta ya ha sido devuelta.")
            return

        if not messagebox.askyesno("Confirmar Devolución",
                                   f"¿Estás seguro de devolver la venta ID {venta_id} por {total}? Se repondrá el stock y se ajustará la ganancia de caja."):
            return

        try:
            # 1. Analizar los detalles para reponer el stock
            items = detalles.split(' | ')
            for item in items:
                # Ejemplo: 'Producto A (2 x $10.00)'
                # Extraemos Nombre, Cantidad, Precio
                nombre = item.split('(')[0].strip()
                cantidad_precio = item.split('(')[1].replace(')', '')
                cantidad = int(cantidad_precio.split(' x ')[0])

                # Buscamos el ID del producto por nombre (o ajustamos la lógica si se usaran códigos)
                self.cursor.execute("SELECT id FROM productos WHERE nombre=?", (nombre,))
                prod_result = self.cursor.fetchone()

                if prod_result:
                    prod_id = prod_result[0]
                    # Reponer stock
                    self.cursor.execute("UPDATE productos SET stock = stock + ? WHERE id=?", (cantidad, prod_id))
                else:
                    # En un sistema real, esto debería registrarse, pero por simplicidad mostramos error
                    messagebox.showwarning("Error Parcial", f"No se pudo reponer el stock para '{nombre}'.")
                    # No hacemos un 'continue', intentamos seguir con la transacción

            # 2. Marcar la venta como devolución en la BD
            self.cursor.execute("UPDATE ventas SET es_devolucion=1 WHERE id=?", (venta_id,))

            # 3. Ajustar la ganancia de la caja (asumiendo que total es ganancia bruta en este sistema)
            total_devuelto = float(total.replace('$', ''))

            if self.caja_abierta:
                self.ganancia_caja_actual -= total_devuelto
                self.cursor.execute("UPDATE caja SET ganancia_total=? WHERE id=?",
                                    (self.ganancia_caja_actual, self.current_caja_id))

            self.conn.commit()

            messagebox.showinfo("Éxito",
                                f"Devolución de Venta ID {venta_id} procesada exitosamente. Stock repuesto y caja ajustada.")

            self.cargar_productos()
            self.cargar_registros_ventas()
            self.update_caja_gui()

        except Exception as e:
            self.conn.rollback()
            messagebox.showerror("Error de Devolución", f"Ocurrió un error al procesar la devolución: {e}")

    # --- Sobreescribir Cargar Ventas ---

    def cargar_registros_ventas(self):
        for item in self.ventas_tree.get_children():
            self.ventas_tree.delete(item)

        # Consulta que incluye la columna 'es_devolucion'
        self.cursor.execute("SELECT id, fecha, total, detalles, es_devolucion FROM ventas ORDER BY id DESC")
        ventas = self.cursor.fetchall()

        for venta in ventas:
            venta_id, fecha, total, detalles, es_devolucion = venta

            estado_display = "DEVOLUCIÓN" if es_devolucion else "VENDIDO"
            tag = "devolucion" if es_devolucion else "vendido"

            self.ventas_tree.insert("", "end", values=(
                venta_id,
                fecha.split(' ')[0],
                f"${total:.2f}",
                detalles,
                estado_display
            ), tags=(tag,))

        # Configurar tags visuales
        self.ventas_tree.tag_configure("devolucion", background='#f8d7da',
                                       foreground='#721c24')  # Rojo claro/Oscuro para devolución
        self.ventas_tree.tag_configure("vendido", background='white', foreground='black')

    # ====================================================================
    #           MÉTODOS INALTERADOS
    # ====================================================================

    def cargar_productos(self, busqueda=""):
        # ... (Función de cargar productos sin cambios) ...
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

        self.cursor.execute("SELECT id, nombre, categoria, descripcion, stock, precio FROM productos WHERE id=?",
                            (producto_id,))
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

            # Deshabilitar stock en modo edición (se usa el formulario de Recepción para aumento)
            if mode == "Editar" and field == "Stock":
                entries[field].config(state=DISABLED)

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

            if mode == "Agregar":
                stock = int(entries["Stock"].get())
            else:
                self.cursor.execute("SELECT stock FROM productos WHERE id=?", (producto_id,))
                stock = self.cursor.fetchone()[0]  # Mantiene el stock actual

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
                    "UPDATE productos SET nombre=?, categoria=?, descripcion=?, precio=? WHERE id=?",
                    (nombre, categoria, descripcion, precio, producto_id))
                messagebox.showinfo("Éxito", "Producto editado correctamente.")

            self.conn.commit()
            self.cargar_productos()
            top_window.destroy()

        except ValueError as e:
            messagebox.showerror("Error de Validación", str(e))
        except Exception as e:
            messagebox.showerror("Error de BD", f"Ocurrió un error al guardar: {e}")

    def eliminar_producto(self):
        # ... (Función de eliminar producto sin cambios) ...
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
        # ... (Función de chequear estado de caja sin cambios) ...
        self.cursor.execute("SELECT id, ganancia_total FROM caja WHERE estado='Abierta' ORDER BY id DESC LIMIT 1")
        last_caja = self.cursor.fetchone()

        if last_caja:
            self.caja_abierta = True
            self.current_caja_id = last_caja[0]
            self.ganancia_caja_actual = last_caja[1]
            self.update_caja_gui()
        else:
            self.caja_abierta = False
            self.current_caja_id = None
            self.ganancia_caja_actual = 0.0
            self.update_caja_gui()

    def toggle_caja(self):
        # ... (Función de abrir/cerrar caja sin cambios) ...
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
        # ... (Función de actualizar GUI de caja sin cambios) ...
        if self.caja_abierta:
            self.caja_status_label.config(text=f"CAJA ABIERTA | Ganancia: ${self.ganancia_caja_actual:.2f}",
                                          bootstyle="success")
            self.caja_button.config(text="Cerrar Caja", bootstyle="danger")
        else:
            self.caja_status_label.config(text="CAJA CERRADA", bootstyle="danger")
            self.caja_button.config(text="Abrir Caja", bootstyle="success")

    def add_to_carrito(self):
        # ... (Función de añadir al carrito sin cambios) ...
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
        # ... (Función de actualizar GUI del carrito sin cambios) ...
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
        # ... (Función de vaciar carrito sin cambios) ...
        if self.productos_carrito:
            if messagebox.askyesno("Confirmar", "¿Deseas vaciar el carrito actual?"):
                self.productos_carrito = {}
                self.update_carrito_gui()

    def finalizar_venta(self):
        # ... (Función de finalizar venta sin cambios en lógica central) ...
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
        # La nueva columna 'es_devolucion' tiene un DEFAULT 0, no necesitamos especificarla aquí.
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

    def exportar_a_excel(self):
        # ... (Función de exportar a Excel sin cambios) ...
        if not EXPORT_AVAILABLE:
            messagebox.showerror("Error de Exportación", "Las librerías 'pandas' y 'reportlab' no están instaladas.")
            return

        try:
            # Consulta actualizada para obtener la columna es_devolucion
            self.cursor.execute("SELECT id, fecha, total, detalles, es_devolucion FROM ventas ORDER BY id DESC")
            data = self.cursor.fetchall()

            if not data:
                messagebox.showwarning("Advertencia", "No hay registros de ventas para exportar.")
                return

            columnas = ["ID Venta", "Fecha", "Total", "Detalles de Venta", "Es Devolución (1/0)"]
            df = pd.DataFrame(data, columns=columnas)

            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Archivos Excel", "*.xlsx")],
                title="Guardar Registro de Ventas (Excel)"
            )

            if filepath:
                df.to_excel(filepath, index=False)
                messagebox.showinfo("Éxito", f"Datos exportados a Excel:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"Ocurrió un error al exportar a Excel: {e}")

    def exportar_a_pdf(self):
        # ... (Función de exportar a PDF sin cambios) ...
        if not EXPORT_AVAILABLE:
            messagebox.showerror("Error de Exportación", "Las librerías 'pandas' y 'reportlab' no están instaladas.")
            return

        try:
            # Consulta actualizada para obtener la columna es_devolucion
            self.cursor.execute("SELECT id, fecha, total, detalles, es_devolucion FROM ventas ORDER BY id DESC")
            data = self.cursor.fetchall()

            if not data:
                messagebox.showwarning("Advertencia", "No hay registros de ventas para exportar.")
                return

            filepath = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                title="Guardar Registro de Ventas (PDF)"
            )

            if not filepath:
                return

            doc = SimpleDocTemplate(filepath, pagesize=letter)
            styles = getSampleStyleSheet()
            elementos = []

            elementos.append(Paragraph("REPORTE DE HISTORIAL DE VENTAS", styles['h1']))
            elementos.append(Paragraph(f"Fecha de Reporte: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                       styles['Normal']))
            elementos.append(Paragraph("<br/>", styles['Normal']))

            header = ["ID Venta", "Fecha", "Total", "Detalles", "Estado"]
            table_data = [header]
            total_ventas = 0.0

            for row in data:
                total_str = f"${row[2]:.2f}"
                if row[4] == 0:
                    total_ventas += row[2]  # Solo suma las ventas no devueltas al total general
                    estado = "VENDIDO"
                else:
                    estado = "DEVOLUCIÓN"

                table_data.append([row[0], row[1].split(' ')[0], total_str, row[3], estado])

            table = Table(table_data, colWidths=[50, 80, 70, 270, 70])

            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ])
            table.setStyle(style)
            elementos.append(table)

            elementos.append(Paragraph("<br/>", styles['Normal']))
            elementos.append(
                Paragraph(f"TOTAL NETO DE VENTAS (SIN DEVOLUCIONES): <font color='red'>${total_ventas:.2f}</font>",
                          styles['h3']))

            doc.build(elementos)
            messagebox.showinfo("Éxito", f"Datos exportados a PDF:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error de Exportación",
                                 f"Ocurrió un error al exportar a PDF. Error: {e}")

    def cargar_registros_caja(self):
        # ... (Función de cargar registros de caja sin cambios) ...
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