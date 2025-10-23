import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
from ttkbootstrap import Style


class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Punto de Venta (POS) - Tienda")

        # 1. Configuración de Estilo y Tema (ttkbootstrap)
        self.style = Style(theme='cosmo')  # Puedes probar otros temas como 'flatly', 'lumen', 'superhero'
        self.style.configure("TLabel", font=("Helvetica", 10))
        self.style.configure("TButton", font=("Helvetica", 10, "bold"))

        # 2. Inicializar la Base de Datos
        self.conn = sqlite3.connect('pos_data.db')
        self.cursor = self.conn.cursor()
        self.setup_database()

        # 3. Variables de la Aplicación
        self.caja_abierta = False
        self.productos_carrito = {}  # {id_producto: {'nombre': ..., 'precio': ..., 'cantidad': ...}}
        self.ganancia_caja_actual = 0.0

        # 4. Crear la Interfaz de Usuario
        self.create_widgets()

        # 5. Cargar productos al iniciar
        self.cargar_productos()

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
    #           SECCIÓN DE WIDGETS Y GUI
    # ====================================================================

    def create_widgets(self):
        # Contenedor principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Paneles principales
        panel_productos = ttk.LabelFrame(main_frame, text="Gestión de Productos", padding="10")
        panel_productos.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        panel_ventas = ttk.LabelFrame(main_frame, text="Punto de Venta (Caja)", padding="10")
        panel_ventas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        panel_registros = ttk.LabelFrame(main_frame, text="Registros de Ventas y Caja", padding="10")
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
        ttk.Label(frame, text="Buscar Producto:").grid(row=0, column=0, pady=5, sticky='w')
        self.search_entry = ttk.Entry(frame, width=30)
        self.search_entry.grid(row=0, column=1, pady=5, padx=5, sticky='ew')
        self.search_entry.bind('<KeyRelease>', self.buscar_producto)  # Búsqueda en tiempo real

        # Treeview de Productos
        columns = ("ID", "Nombre", "Categoría", "Stock", "Precio")
        self.productos_tree = ttk.Treeview(frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.productos_tree.heading(col, text=col)
            self.productos_tree.column(col, width=100, anchor='center')
        self.productos_tree.column("ID", width=40)
        self.productos_tree.column("Nombre", width=150)
        self.productos_tree.grid(row=1, column=0, columnspan=3, pady=10, sticky='nsew')

        # Scrollbar para el Treeview
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.productos_tree.yview)
        vsb.grid(row=1, column=3, sticky='ns')
        self.productos_tree.configure(yscrollcommand=vsb.set)

        # Frame de Botones de Producto
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)

        ttk.Button(btn_frame, text="➕ Agregar Producto", command=self.open_agregar_producto, bootstyle="success").pack(
            side='left', padx=5)
        ttk.Button(btn_frame, text="✏️ Editar Producto", command=self.open_editar_producto, bootstyle="info").pack(
            side='left', padx=5)
        ttk.Button(btn_frame, text="🗑️ Eliminar Producto", command=self.eliminar_producto, bootstyle="danger").pack(
            side='left', padx=5)

        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(1, weight=1)

    # --------------------------------------------------------------------
    #                           Punto de Venta (Caja)
    # --------------------------------------------------------------------

    def create_venta_widgets(self, frame):
        # Control de Caja (Apertura/Cierre)
        caja_frame = ttk.LabelFrame(frame, text="Control de Caja", padding=10)
        caja_frame.pack(fill='x', pady=5)
        self.caja_status_label = ttk.Label(caja_frame, text="Caja Cerrada", bootstyle="danger",
                                           font=("Helvetica", 12, "bold"))
        self.caja_status_label.pack(side='left', padx=10)
        self.caja_button = ttk.Button(caja_frame, text="Abrir Caja", command=self.toggle_caja, bootstyle="success")
        self.caja_button.pack(side='right')

        # Selección de Producto para Venta
        ttk.Label(frame, text="Buscar Producto para Venta (ID/Nombre):").pack(fill='x', pady=5)
        self.venta_search_entry = ttk.Entry(frame)
        self.venta_search_entry.pack(fill='x', pady=5)

        add_frame = ttk.Frame(frame)
        add_frame.pack(fill='x', pady=5)
        ttk.Label(add_frame, text="Cantidad:").pack(side='left')
        self.cantidad_entry = ttk.Entry(add_frame, width=5)
        self.cantidad_entry.pack(side='left', padx=5)
        ttk.Button(add_frame, text="🛒 Añadir al Carrito", command=self.add_to_carrito, bootstyle="primary").pack(
            side='right')

        # Treeview del Carrito
        self.carrito_tree = ttk.Treeview(frame, columns=("Nombre", "Cantidad", "Precio Unitario", "Subtotal"),
                                         show='headings', height=8)
        self.carrito_tree.heading("Nombre", text="Producto")
        self.carrito_tree.heading("Cantidad", text="Cant.")
        self.carrito_tree.heading("Precio Unitario", text="P. Unit.")
        self.carrito_tree.heading("Subtotal", text="Subtotal")
        self.carrito_tree.column("Cantidad", width=50, anchor='center')
        self.carrito_tree.column("Precio Unitario", width=80, anchor='e')
        self.carrito_tree.column("Subtotal", width=80, anchor='e')
        self.carrito_tree.pack(fill='both', expand=True, pady=10)

        # Total de la Venta
        total_frame = ttk.Frame(frame)
        total_frame.pack(fill='x', pady=10)
        ttk.Label(total_frame, text="TOTAL:", font=("Helvetica", 14, "bold")).pack(side='left')
        self.total_label = ttk.Label(total_frame, text="$0.00", font=("Helvetica", 16, "bold"), bootstyle="primary")
        self.total_label.pack(side='right')

        # Botón de Finalizar Venta
        ttk.Button(frame, text="💰 Finalizar Venta", command=self.finalizar_venta, bootstyle="success").pack(fill='x',
                                                                                                            pady=5)
        ttk.Button(frame, text="❌ Vaciar Carrito", command=self.vaciar_carrito, bootstyle="warning").pack(fill='x')

    # --------------------------------------------------------------------
    #                           Registros y Ventas
    # --------------------------------------------------------------------

    def create_registros_widgets(self, frame):
        notebook = ttk.Notebook(frame)
        notebook.pack(expand=True, fill="both")

        # Pestaña de Ventas
        ventas_frame = ttk.Frame(notebook, padding=5)
        notebook.add(ventas_frame, text="Historial de Ventas")

        columns_ventas = ("ID Venta", "Fecha", "Total", "Detalles")
        self.ventas_tree = ttk.Treeview(ventas_frame, columns=columns_ventas, show='headings', height=5)
        for col in columns_ventas:
            self.ventas_tree.heading(col, text=col)
            self.ventas_tree.column(col, width=150, anchor='center')
        self.ventas_tree.pack(fill='both', expand=True)

        # Pestaña de Caja y Ganancias
        caja_frame = ttk.Frame(notebook, padding=5)
        notebook.add(caja_frame, text="Registro de Cajas")

        columns_caja = ("ID Caja", "Estado", "Apertura", "Cierre", "Ganancia")
        self.caja_tree = ttk.Treeview(caja_frame, columns=columns_caja, show='headings', height=5)
        for col in columns_caja:
            self.caja_tree.heading(col, text=col)
            self.caja_tree.column(col, width=120, anchor='center')
        self.caja_tree.pack(fill='both', expand=True)

        # Cargar registros al iniciar
        self.cargar_registros_ventas()
        self.cargar_registros_caja()

    # ====================================================================
    #           SECCIÓN DE FUNCIONALIDAD DE PRODUCTOS
    # ====================================================================

    def cargar_productos(self, busqueda=""):
        # Limpiar Treeview
        for item in self.productos_tree.get_children():
            self.productos_tree.delete(item)

        query = "SELECT id, nombre, categoria, stock, precio FROM productos"
        if busqueda:
            # Buscar por nombre, categoría o ID
            query += f" WHERE nombre LIKE '%{busqueda}%' OR categoria LIKE '%{busqueda}%' OR id LIKE '{busqueda}%'"

        self.cursor.execute(query)
        productos = self.cursor.fetchall()

        for prod in productos:
            # prod: (id, nombre, categoria, stock, precio)
            stock_str = f"⚠️ {prod[3]}" if prod[3] < 5 else prod[3]
            self.productos_tree.insert("", "end", values=(prod[0], prod[1], prod[2], stock_str, f"${prod[4]:.2f}"))

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

        # Obtener el ID del producto seleccionado
        producto_id = self.productos_tree.item(selected_item, 'values')[0]

        self.cursor.execute("SELECT * FROM productos WHERE id=?", (producto_id,))
        producto = self.cursor.fetchone()  # (id, nombre, categoria, descripcion, stock, precio)

        if producto:
            self.create_producto_form_window("Editar", producto)
        else:
            messagebox.showerror("Error", "Producto no encontrado en la base de datos.")

    def create_producto_form_window(self, mode, producto=None):
        # producto = (id, nombre, categoria, descripcion, stock, precio)
        top = tk.Toplevel(self.root)
        top.title(f"{mode} Producto")
        top.grab_set()  # Bloquear ventana principal

        frame = ttk.Frame(top, padding=10)
        frame.pack(padx=10, pady=10)

        fields = ["Nombre", "Categoría", "Descripción", "Stock", "Precio"]
        entries = {}

        for i, field in enumerate(fields):
            ttk.Label(frame, text=f"{field}:").grid(row=i, column=0, pady=5, sticky='w')
            entry = ttk.Entry(frame, width=40)
            entry.grid(row=i, column=1, pady=5, padx=5, sticky='ew')
            entries[field] = entry

        # Precargar datos en modo "Editar"
        if mode == "Editar" and producto:
            entries["Nombre"].insert(0, producto[1])
            entries["Categoría"].insert(0, producto[2])
            entries["Descripción"].insert(0, producto[3])
            entries["Stock"].insert(0, str(producto[4]))
            entries["Precio"].insert(0, str(producto[5]))

            action_command = lambda: self.guardar_producto(mode, top, entries, producto[0])
        else:
            action_command = lambda: self.guardar_producto(mode, top, entries)

        ttk.Button(frame, text=mode, command=action_command, bootstyle="success").grid(row=len(fields), column=0,
                                                                                       columnspan=2, pady=10)

        top.grid_columnconfigure(0, weight=1)  # Centrar el frame

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
            self.cargar_productos()  # Refrescar la tabla
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

    # ====================================================================
    #           SECCIÓN DE FUNCIONALIDAD DE VENTA Y CAJA
    # ====================================================================

    def check_caja_status(self):
        # Busca la última caja abierta sin cerrar
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
            # Cerrar Caja
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
            # Abrir Caja
            fecha_apertura = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT INTO caja (estado, fecha_apertura, ganancia_total) VALUES (?, ?, ?)",
                                ('Abierta', fecha_apertura, 0.0))
            self.conn.commit()
            self.current_caja_id = self.cursor.lastrowid
            self.caja_abierta = True
            messagebox.showinfo("Caja Abierta", "Caja abierta. Puedes empezar a vender.")

        self.update_caja_gui()
        self.vaciar_carrito()  # Por si acaso

    def update_caja_gui(self):
        if self.caja_abierta:
            self.caja_status_label.config(text=f"Caja Abierta | Ganancia: ${self.ganancia_caja_actual:.2f}",
                                          bootstyle="success")
            self.caja_button.config(text="Cerrar Caja", bootstyle="danger")
        else:
            self.caja_status_label.config(text="Caja Cerrada", bootstyle="danger")
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

        # Buscar el producto por ID o Nombre
        query = "SELECT id, nombre, stock, precio FROM productos WHERE id=? OR nombre LIKE ?"
        self.cursor.execute(query, (search_term, f'%{search_term}%'))
        productos = self.cursor.fetchall()

        if not productos:
            messagebox.showerror("Error", "Producto no encontrado.")
            return

        # Si hay más de uno, tomamos el primero (o implementar un selector si es necesario, por ahora simplificamos)
        producto = productos[0]
        prod_id, nombre, stock_actual, precio = producto

        if cantidad > stock_actual:
            messagebox.showwarning("Stock Insuficiente", f"Solo hay {stock_actual} unidades de '{nombre}' en stock.")
            return

        # Actualizar el Carrito
        if prod_id in self.productos_carrito:
            # Si ya está, sumar cantidad
            self.productos_carrito[prod_id]['cantidad'] += cantidad
        else:
            # Si es nuevo, agregarlo
            self.productos_carrito[prod_id] = {
                'nombre': nombre,
                'precio': precio,
                'cantidad': cantidad
            }

        self.venta_search_entry.delete(0, tk.END)
        self.cantidad_entry.delete(0, tk.END)

        self.update_carrito_gui()

    def update_carrito_gui(self):
        # Limpiar Treeview
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
        ganancia_bruta = 0.0  # Simplificación: asumimos que TotalVenta = Ganancia para el registro de caja

        # 1. Actualizar el Stock y construir los detalles
        for prod_id, data in self.productos_carrito.items():
            cantidad = data['cantidad']
            precio = data['precio']
            nombre = data['nombre']

            # Reducir Stock
            self.cursor.execute("UPDATE productos SET stock = stock - ? WHERE id=?", (cantidad, prod_id))

            # Construir detalle para el registro de ventas
            detalles_venta.append(f"{nombre} ({cantidad} x ${precio:.2f})")

            # Sumar al total de ganancia (simplificado)
            ganancia_bruta += (precio * cantidad)

        # 2. Registrar la Venta
        detalles_str = " | ".join(detalles_venta)
        self.cursor.execute("INSERT INTO ventas (fecha, total, detalles) VALUES (?, ?, ?)",
                            (fecha_venta, total_venta, detalles_str))

        # 3. Actualizar la Ganancia de Caja
        self.ganancia_caja_actual += ganancia_bruta
        self.cursor.execute("UPDATE caja SET ganancia_total=? WHERE id=?",
                            (self.ganancia_caja_actual, self.current_caja_id))

        self.conn.commit()

        # 4. Limpiar y Refrescar
        messagebox.showinfo("Venta Exitosa", f"Venta registrada por ${total_venta:.2f}")
        self.productos_carrito = {}
        self.update_carrito_gui()
        self.cargar_productos()  # Refrescar tabla de productos para mostrar stock reducido
        self.cargar_registros_ventas()  # Refrescar historial
        self.update_caja_gui()  # Actualizar ganancia en el label de caja

    # ====================================================================
    #           SECCIÓN DE REGISTROS
    # ====================================================================

    def cargar_registros_ventas(self):
        # Limpiar Treeview
        for item in self.ventas_tree.get_children():
            self.ventas_tree.delete(item)

        self.cursor.execute("SELECT id, fecha, total, detalles FROM ventas ORDER BY id DESC")
        ventas = self.cursor.fetchall()

        for venta in ventas:
            # venta: (id, fecha, total, detalles)
            self.ventas_tree.insert("", "end", values=(venta[0], venta[1].split(' ')[0], f"${venta[2]:.2f}", venta[3]))

    def cargar_registros_caja(self):
        # Limpiar Treeview
        for item in self.caja_tree.get_children():
            self.caja_tree.delete(item)

        self.cursor.execute(
            "SELECT id, estado, fecha_apertura, fecha_cierre, ganancia_total FROM caja ORDER BY id DESC")
        cajas = self.cursor.fetchall()

        for caja in cajas:
            # caja: (id, estado, fecha_apertura, fecha_cierre, ganancia_total)
            fecha_cierre_disp = caja[3].split(' ')[0] if caja[3] else "N/A"
            self.caja_tree.insert("", "end", values=(
                caja[0],
                caja[1],
                caja[2].split(' ')[0],  # Solo fecha de apertura
                fecha_cierre_disp,
                f"${caja[4]:.2f}"
            ), tags=caja[1])  # Usar estado como tag para estilos

            # Aplicar estilo al estado de caja
            if caja[1] == 'Abierta':
                self.caja_tree.tag_configure("Abierta", background='#d4edda', foreground='#155724')  # Verde claro
            elif caja[1] == 'Cerrada':
                self.caja_tree.tag_configure("Cerrada", background='#f8d7da', foreground='#721c24')  # Rojo claro


# ====================================================================
#           EJECUCIÓN PRINCIPAL
# ====================================================================

if __name__ == "__main__":
    # Inicializa el root de Tkinter (Ventana principal)
    root = tk.Tk()

    # Crea la instancia de la aplicación
    app = POSApp(root)

    # Ejecuta el bucle principal de la interfaz
    root.mainloop()