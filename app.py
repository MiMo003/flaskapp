from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify, make_response, send_file
import psycopg2  # Usamos psycopg2 para conectarnos a PostgreSQL
from psycopg2.extras import RealDictCursor
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import timedelta
from fpdf import FPDF
from dotenv import load_dotenv
import bcrypt
from weasyprint import HTML
import io
import os

# Cargar las variables desde el archivo .env
load_dotenv(verbose=True)

DATABASE_URL = os.getenv('DATABASE_URL')

# Configuración de la aplicación Flask
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['DEBUG'] = False
app.config['ENV'] = 'Production'
app.secret_key = 'mysecretkey'

def get_db_connection():
    connection = psycopg2.connect(DATABASE_URL)
    connection.set_client_encoding('UTF8')  # Asegura que se use UTF-8 para la codificación
    return connection

# Carpeta para cargar archivos
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Permitir solo ciertos tipos de archivo
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/generar_pdf/<int:pedido_id>/<int:cliente_id>')
def generar_pdf(pedido_id, cliente_id):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"PDF del Pedido ID: {pedido_id}", ln=True, align='C')
    pdf.cell(200, 10, txt="Detalles del Pedido y Cliente", ln=True, align='C')
    pdf.ln(10)

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Consulta para obtener detalles del pedido
            query_pedido = '''
            SELECT 
                g.id AS pedido_id, 
                g.cod, 
                pp.id AS producto_id, 
                pp.codProducto, 
                pp.nombreProducto, 
                pp.precio, 
                pp.cantidad, 
                m.id AS modelo_id, 
                m.nombre AS modelo_nombre, 
                m.imagen AS modelo_imagen
            FROM guiapedido g
            LEFT JOIN productopedido pp ON g.id = pp.pedidoId
            LEFT JOIN modelo m ON pp.codProducto = m.id
            WHERE g.id = %s;
            '''
            cursor.execute(query_pedido, (pedido_id,))
            pedido = cursor.fetchall()

            # Consulta para obtener detalles del cliente
            query_cliente = '''
            SELECT 
                c.nombre, 
                c.apellido, 
                c.cuitDni, 
                c.direccion, 
                c.telefono, 
                c.email
            FROM cliente c
            WHERE c.id = %s
            '''
            cursor.execute(query_cliente, (cliente_id,))
            cliente = cursor.fetchone()

            if not pedido:
                pdf.cell(200, 10, txt=f"No se encontró el pedido con ID {pedido_id}", ln=True, align='L')
            elif not cliente:
                pdf.cell(200, 10, txt=f"No se encontró el cliente con ID {cliente_id}", ln=True, align='L')
            else:
                # Datos del pedido con el código y número del pedido
                pdf.cell(200, 10, txt="Datos del Pedido:", ln=True, align='L')
                pdf.cell(200, 10, txt=f"Número de Pedido: {pedido[0]['pedido_id']}", ln=True, align='L')
                pdf.cell(200, 10, txt=f"Código de Pedido: {pedido[0]['cod']}", ln=True, align='L')
                pdf.ln(10)

                # Datos del cliente
                pdf.cell(200, 10, txt="Datos del Cliente:", ln=True, align='L')
                pdf.cell(200, 10, txt=f"Nombre: {cliente['nombre']} {cliente['apellido']}", ln=True, align='L')
                pdf.cell(200, 10, txt=f"DNI: {cliente['cuitDni']}", ln=True, align='L')
                pdf.cell(200, 10, txt=f"Dirección: {cliente['direccion']}", ln=True, align='L')
                pdf.cell(200, 10, txt=f"Teléfono: {cliente['telefono']}", ln=True, align='L')
                pdf.cell(200, 10, txt=f"Email: {cliente['email']}", ln=True, align='L')

                pdf.ln(10)

                # Mostrar productos en pequeños recuadros, con imagen, precio y cantidad
                pdf.set_font("Arial", size=10)
                count = 0
                for producto in pedido:
                    if producto['producto_id'] is not None:
                        # Celdas para cada producto con imagen, precio y cantidad
                        pdf.cell(60, 60, border=1, align='C')
                        pdf.ln(10)  # Espacio entre el borde y el contenido

                        # Producto: Imagen, Precio y Cantidad dentro del mismo recuadro
                        if producto['modelo_imagen']:
                            image_path = f"static/images/{producto['modelo_imagen']}"
                            if os.path.exists(image_path):
                                pdf.image(image_path, x=pdf.get_x() + 10, y=pdf.get_y(), w=40, h=40)
                        pdf.ln(40)  # Asegura que la imagen no se cruce con los demás elementos

                        # Precio
                        pdf.cell(60, 10, f"Precio: ${producto['precio']:.2f}", ln=True, align='C')

                        # Cantidad
                        pdf.cell(60, 10, f"Cantidad: {producto['cantidad']}", ln=True, align='C')

                        # Asegura que los productos se presenten uno debajo del otro
                        pdf.ln(10)
                        count += 1

    finally:
        connection.close()

    pdf_buffer = io.BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin1')
    pdf_buffer.write(pdf_output)
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer, 
        as_attachment=True, 
        download_name=f'pedido_{pedido_id}_cliente_{cliente_id}.pdf', 
        mimetype='application/pdf'
    )

# Función para encriptar la contraseña
def encrypt_password(password: str) -> bytes:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Convierte el hash almacenado en bytes antes de compararlo
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def crear_credencial():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM credencial LIMIT 1")  # Se hace una consulta más eficiente para solo obtener una fila
        existe = cursor.fetchone()

        if not existe:  # Si no existe, lo creamos
            password = 'root'
            hashed_password = encrypt_password(password)  # Encripta la contraseña
            hashed_password = hashed_password.decode('utf-8')  # Convierte a string
            
            cursor.execute(
                """INSERT INTO credencial 
                (nombre, color, password, usuarios, permisos, 
                banners, categorias, promociones, historial, 
                ventasrealizadas, prodmasvendidos, productos, pedidos) 
                VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""", 
                ('Admin', '#005919', hashed_password, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
            )
            connection.commit()

    connection.close()

# Llamar la función para crear la credencial
crear_credencial()

def crear_admin():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Verificar si ya existe un empleado con id_credencial = 1 (Admin)
            cursor.execute("SELECT id FROM empleados WHERE id_credencial = 1 LIMIT 1;")
            existe = cursor.fetchone()

            if not existe:  # Si no existe, lo creamos
                cursor.execute("""
                    INSERT INTO empleados (nombre, apellido, email, telefono, id_credencial) 
                    VALUES (NULL, NULL, NULL, NULL, 1);
                """)
                connection.commit()
                print("Empleado inicial creado con credencial de Admin.")
    except Exception as e:
        print(f"Error al crear el empleado inicial: {e}")
    finally:
        if connection:
            connection.close()

crear_admin()

# Función para eliminar productos con cantidad 0 en PostgreSQL
def eliminar_productos_cantidad_0(cursor, connection):
    try:
        # Consultar productos con cantidad 0
        query = "SELECT id FROM productopedido WHERE cantidad = 0"
        cursor.execute(query)
        productos_a_eliminar = cursor.fetchall()

        if productos_a_eliminar:
            # Eliminar productos con cantidad 0
            delete_query = "DELETE FROM productopedido WHERE cantidad = 0"
            cursor.execute(delete_query)
            connection.commit()

            print(f"✅ {len(productos_a_eliminar)} productos eliminados.")
        else:
            print("✅ No hay productos con cantidad 0 para eliminar.")

    except Exception as e:
        print(f"❌ Error al eliminar productos: {str(e)}")

# Función para eliminar pedidos sin productos en PostgreSQL
def eliminar_pedido_sin_productos(cursor, connection):
    try:
        # Obtener todos los pedidos
        query = "SELECT id FROM guiapedido"
        cursor.execute(query)
        pedidos = cursor.fetchall()

        for pedido in pedidos:
            pedido_id = pedido['id']  # Para psycopg2, asegúrate de usar el índice correcto si no es un RealDictCursor

            # Verificar cuántos productos están asociados a este pedido
            check_query = """
            SELECT COUNT(*) as productos_count
            FROM productopedido
            WHERE "pedidoId" = %s
            """
            cursor.execute(check_query, (pedido_id,))
            productos_count = cursor.fetchone()['productos_count']

            if productos_count == 0:
                # Eliminar el pedido si no tiene productos asociados
                delete_query = 'DELETE FROM guiapedido WHERE id = %s'
                cursor.execute(delete_query, (pedido_id,))
                connection.commit()

                print(f"✅ Pedido ID {pedido_id} eliminado porque no tiene productos asociados.")

    except Exception as e:
        print(f"❌ Error al eliminar pedidos: {str(e)}")

# Función para comprobar si un archivo tiene una extensión permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def insertar_backup(connection, idBorrado, motivo, categoria, accion, usuario=None, nombreUser=None, mailUser=None, fechaCambio=None, credencial=None):
    """Inserta un registro en la tabla backupprecioventa con la fecha del mismo día."""
    try:
        with connection.cursor() as cursor:
            # Consulta SQL para insertar el registro
            sql = """
                INSERT INTO backupprecioventa 
                (idBorrado, motivo, categoria, accion, usuario, nombreUser, mailUser, fechaCambio, credencial)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores = (
                idBorrado,
                motivo,
                categoria,
                accion,
                usuario,
                nombreUser,
                mailUser,
                fechaCambio if fechaCambio else datetime.today().strftime('%Y-%m-%d'),
                credencial
            )

            cursor.execute(sql, valores)
            connection.commit()

        return {"mensaje": "Registro agregado exitosamente"}

    except psycopg2.Error as e:
        return {"error": f"Error en la base de datos: {str(e)}"}
    
    except Exception as e:
        return {"error": f"Error inesperado: {str(e)}"}

@app.route('/password', methods=['GET', 'POST'])
def password():
    if request.method == 'POST':
        try:
            data = request.json
            password_recibida = data.get("password")

            if not password_recibida:
                return jsonify({"valid": False, "error": "La contraseña no puede estar vacía."})

            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM credencial")
                credenciales = cursor.fetchall()

                for credencial in credenciales:
                    hashed_password = credencial["password"]
                    print(f"Contraseña almacenada en la base de datos: {hashed_password}")
                    print(f"Contraseña ingresada: {password_recibida}")

                    # Usar verify_password para comparar la contraseña ingresada con la encriptada
                    if verify_password(password_recibida, hashed_password):
                        session["credencial"] = credencial["id"]  # Guardar la sesión
                        return jsonify({
                            "valid": True,
                            "redirect": url_for('config'),
                            "credencial": credencial
                        })

        except psycopg2Error as e:
            return jsonify({"valid": False, "error": str(e)}), 500
        except Exception as e:
            return jsonify({"valid": False, "error": str(e)}), 500
        finally:
            connection.close()

        return jsonify({"valid": False, "error": "Contraseña incorrecta."})

    # Si la solicitud es GET, verificar si hay una credencial en sesión y enviarla a la plantilla
    credencial_data = None
    if "credencial" in session:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM credencial WHERE id = %s", (session["credencial"],))
            credencial_data = cursor.fetchone()
        connection.close()

    return render_template('password.html', credencial=credencial_data)

@app.route('/verificar_sesion')
def verificar_sesion():
    return jsonify({"activa": "credencial" in session})

def verificar_permiso(permiso):
    if "credencial" not in session:
        return False  # No hay sesión activa

    connection = get_db_connection()
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT * FROM credencial WHERE id = %s", (session["credencial"],))
        credencial = cursor.fetchone()

    connection.close()

    if not credencial or not credencial.get(permiso):
        return False  # Si la credencial no existe o no tiene el permiso, denegar acceso

    return True  # Permiso concedido

@app.route('/')
def index():
    connection = get_db_connection()
    cliente_id = request.cookies.get('cliente_id')

    if cliente_id:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM cliente WHERE id = %s", (cliente_id,))
            cliente = cursor.fetchone()

        if not cliente:
            print(f"⚠️ Cliente con ID {cliente_id} no encontrado en la DB. Borrando cookie...")
            response = make_response(redirect(url_for('index')))
            response.set_cookie('cliente_id', '', expires=0)  # Eliminar cookie
            return response

    if not cliente_id or not cliente:
        session_id = str(uuid.uuid4())
        print(f"🔍 Creando nuevo cliente con session_id: {session_id}")

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO cliente (session_id, nombre, apellido, cuitDni, direccion, localidad, provincia, telefono, email, fechaAlta) 
                VALUES (%s, 'Anonimo', 'Anonimo', NULL, '', '', '', '', '', NOW()) 
                RETURNING id;
            """, (session_id,))
            cliente_id = cursor.fetchone()[0]
            connection.commit()
            print(f"✅ Cliente creado con ID: {cliente_id}")

        response = make_response()
        response.set_cookie('cliente_id', str(cliente_id), max_age=60*60*24*30)
    else:
        print(f"🔹 Cliente ya tiene ID en la cookie: {cliente_id}")
        response = make_response()

    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT id, nombre FROM clasearticulo;")
        categorias = cursor.fetchall()

        cursor.execute("SELECT id, nombre, claseArticulo FROM subClase;")
        subcategorias = cursor.fetchall()

    categorias_dict = {cat['id']: {'nombre': cat['nombre'], 'subcategorias': []} for cat in categorias}
    for sub in subcategorias:
        if sub['claseArticulo'] in categorias_dict:
            categorias_dict[sub['claseArticulo']]['subcategorias'].append({'id': sub['id'], 'nombre': sub['nombre']})

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM venta;")
        result = cursor.fetchone()
        total_ventas = result[0] if result else 0

    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        if total_ventas > 0:
            cursor.execute("""
                SELECT a.id, a.nombre, a.cod, a.descripcion, a.unidadVenta, a.precioVenta, a.fechaAlta,
                    (SELECT i.imagen 
                     FROM modelo i 
                     WHERE i.articulo = a.id 
                     ORDER BY i.id ASC 
                     LIMIT 1) AS imagen_url,
                    COALESCE(COUNT(v.id), 0) AS total_vendido
                FROM articulo a
                LEFT JOIN venta v ON a.id = v.producto
                GROUP BY a.id
                ORDER BY total_vendido DESC;
            """)
        else:
            cursor.execute("""
                SELECT a.id, a.nombre, a.cod, a.descripcion, a.unidadVenta, a.precioVenta, a.fechaAlta,
                    (SELECT i.imagen 
                     FROM modelo i 
                     WHERE i.articulo = a.id 
                     ORDER BY i.id ASC 
                     LIMIT 1) AS imagen_url
                FROM articulo a
                ORDER BY a.id DESC
                LIMIT 10;
            """)

        articulos = cursor.fetchall()

    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT a.id, a.nombre, a.cod, a.descripcion, a.unidadVenta, a.precioVenta, a.fechaAlta,
                (SELECT i.imagen 
                 FROM modelo i 
                 WHERE i.articulo = a.id 
                 ORDER BY i.id ASC 
                 LIMIT 1) AS imagen_url
            FROM articulo a
            ORDER BY a.id DESC
            LIMIT 3;
        """)
        ultArt = cursor.fetchall()

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM articulo;")
        result = cursor.fetchone()
        cantArtic = result[0] if result else 0

    response.set_data(render_template('index.html', 
                                      articulos=articulos, 
                                      cantArtic=cantArtic, 
                                      ultArt=ultArt, 
                                      categorias=categorias_dict))
    connection.close()
    return response

@app.route('/catalogo')
def catalogo():
    connection = get_db_connection()
    subclase_id = request.args.get('subclase', type=int)  # Obtener el parámetro de la URL
    cliente_id = request.cookies.get('cliente_id')

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener todas las categorías
            cursor.execute("SELECT id, nombre FROM clasearticulo;")
            categorias = cursor.fetchall()

            # Obtener todas las subcategorías organizadas por categoría
            cursor.execute("SELECT id, nombre, \"claseArticulo\" FROM subClase;")
            subcategorias = cursor.fetchall()

            # Estructurar categorías con sus subcategorías
            categorias_dict = {cat['id']: {'nombre': cat['nombre'], 'subcategorias': []} for cat in categorias}
            for sub in subcategorias:
                if sub['claseArticulo'] in categorias_dict:
                    categorias_dict[sub['claseArticulo']]['subcategorias'].append({
                        'id': sub['id'],
                        'nombre': sub['nombre']
                    })

            # Validar si el subclase_id es válido
            subclase_ids_validos = [sub['id'] for sub in subcategorias]
            if subclase_id and subclase_id not in subclase_ids_validos:
                print(f"⚠️ ID de subclase no válido: {subclase_id}. Redirigiendo al catálogo completo...")
                return redirect(url_for('catalogo'))

            # Contar artículos, con o sin filtro de subclase
            if subclase_id:
                cursor.execute("SELECT COUNT(*) AS total FROM articulo WHERE \"idSubClase\" = %s;", (subclase_id,))
            else:
                cursor.execute("SELECT COUNT(*) AS total FROM articulo;")
            
            result = cursor.fetchone()
            cantArtic = result['total'] if result else 0

            # Consulta de artículos (filtrado o no por subclase)
            query = sql.SQL("""
                SELECT a.id, a.nombre, 
                    (SELECT i.imagen FROM modelo i WHERE i.articulo = a.id ORDER BY i.id ASC LIMIT 1) AS img, 
                    a.descripcion, a.\"precioVenta\"
                FROM articulo a 
                {where_clause}
                ORDER BY a.id DESC 
                LIMIT 10;
            """)
            where_clause = sql.SQL("WHERE a.\"idSubClase\" = %s") if subclase_id else sql.SQL("")
            cursor.execute(query.format(where_clause=where_clause), (subclase_id,) if subclase_id else None)
            articulos = cursor.fetchall()

            # Obtener los 3 últimos artículos
            cursor.execute("""
                SELECT a.id, a.nombre, a.cod, a.descripcion, a.\"unidadVenta\", a.\"precioVenta\", a.\"fechaAlta\",
                    (SELECT i.imagen 
                     FROM modelo i 
                     WHERE i.articulo = a.id 
                     ORDER BY i.id ASC 
                     LIMIT 1) AS imagen_url
                FROM articulo a
                ORDER BY a.id DESC
                LIMIT 3;
            """)
            ultArt = cursor.fetchall()

    except Exception as e:
        print(f"❌ Error al obtener los datos del catálogo: {e}")
        return "Error al cargar el catálogo. Inténtelo de nuevo más tarde.", 500
    finally:
        connection.close()

    return render_template('catalogo.html', 
                           categorias=categorias_dict, 
                           cantArtic=cantArtic, 
                           ultArt=ultArt, 
                           articulos=articulos, 
                           subclase_id=subclase_id)

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Borra toda la sesión
    return jsonify({"success": True, "redirect": url_for('password')})

@app.route('/fqa')
def fqa():
    cliente_id = request.cookies.get('cliente_id')
    connection = get_db_connection()

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener todas las categorías
            cursor.execute("SELECT id, nombre FROM clasearticulo;")
            categorias = cursor.fetchall()

            # Obtener todas las subcategorías organizadas por categoría
            cursor.execute("SELECT id, nombre, \"claseArticulo\" FROM subClase;")
            subcategorias = cursor.fetchall()

        # Estructurar los datos para que cada categoría tenga sus subcategorías
        categorias_dict = {cat['id']: {'nombre': cat['nombre'], 'subcategorias': []} for cat in categorias}

        for sub in subcategorias:
            if sub['claseArticulo'] in categorias_dict:
                categorias_dict[sub['claseArticulo']]['subcategorias'].append({
                    'id': sub['id'], 
                    'nombre': sub['nombre']
                })

        return render_template('fqa.html', categorias=categorias_dict)
    
    except Exception as e:
        print(f"❌ Error al obtener datos de FQA: {e}")
        return "Error al cargar FQA. Inténtelo de nuevo más tarde.", 500
    
    finally:
        connection.close()

@app.route('/producto')
def producto():
    producto_id = request.args.get('id', type=int)
    cliente_id = request.cookies.get('cliente_id')
    
    if not producto_id:
        return "Error: No se recibió el ID del producto", 400

    connection = get_db_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener todas las categorías
            cursor.execute("SELECT id, nombre FROM clasearticulo;")
            categorias = cursor.fetchall()

            # Obtener todas las subcategorías organizadas por categoría
            cursor.execute("SELECT id, nombre, \"claseArticulo\" FROM subClase;")
            subcategorias = cursor.fetchall()

            # Obtener el producto seleccionado
            cursor.execute("SELECT * FROM articulo WHERE id = %s;", (producto_id,))
            producto = cursor.fetchone()

            if not producto:
                return "Error: Producto no encontrado", 404

            # Obtener modelos y sus imágenes asociadas al producto
            cursor.execute("""
                SELECT id, nombre, imagen, stock 
                FROM modelo 
                WHERE articulo = %s;
            """, (producto_id,))
            modelos = cursor.fetchall()

        # Estructurar las categorías y subcategorías
        categorias_dict = {cat['id']: {'nombre': cat['nombre'], 'subcategorias': []} for cat in categorias}
        for sub in subcategorias:
            if sub['claseArticulo'] in categorias_dict:
                categorias_dict[sub['claseArticulo']]['subcategorias'].append({
                    'id': sub['id'], 
                    'nombre': sub['nombre']
                })

        return render_template('producto.html', producto=producto, categorias=categorias_dict, modelos=modelos)
    
    except Exception as e:
        print(f"❌ Error al obtener el producto: {e}")
        return "Error al cargar el producto. Inténtelo de nuevo más tarde.", 500
    
    finally:
        connection.close()

@app.route('/carrito')
def carrito():
    connection = get_db_connection()
    cliente_id = request.cookies.get('cliente_id')

    if not cliente_id:
        return redirect(url_for('index'))  # Si no hay cliente, redirigir a la página principal

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener todas las categorías
            cursor.execute("SELECT id, nombre FROM clasearticulo;")
            categorias = cursor.fetchall()

            # Obtener todas las subcategorías organizadas por categoría
            cursor.execute("SELECT id, nombre, \"claseArticulo\" FROM subClase;")
            subcategorias = cursor.fetchall()

        # Estructurar los datos de categorías
        categorias_dict = {cat['id']: {'nombre': cat['nombre'], 'subcategorias': []} for cat in categorias}
        for sub in subcategorias:
            if sub['claseArticulo'] in categorias_dict:
                categorias_dict[sub['claseArticulo']]['subcategorias'].append({'id': sub['id'], 'nombre': sub['nombre']})

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener el pedido pendiente del cliente
            cursor.execute("""
                SELECT id, cod AS codigo_pedido, totalPago AS total_pago_pedido, fechaIngreso AS fecha_ingreso_pedido, 
                       hora AS hora_pedido, estadoPedido AS estado_pedido 
                FROM guiapedido 
                WHERE cliente_id = %s AND estadoPedido = 'pendiente' 
                LIMIT 1;
            """, (cliente_id,))
            pedido = cursor.fetchone()

            productos = []
            total_calculado = 0  # Inicializar el total

            if pedido:
                pedido_id = pedido['id']

                # Obtener los productos asociados al pedido
                cursor.execute("""
                    SELECT pp.cantidad AS cantidad_producto_pedido, pp.precio AS precio_producto_pedido,
                           m.nombre AS modelo_nombre, m.imagen AS modelo_imagen, 
                           p.nombre AS articulo_nombre
                    FROM productopedido pp
                    JOIN modelo m ON pp.codProducto = m.id
                    JOIN articulo p ON p.id = m.articulo
                    WHERE pp.pedidoId = %s;
                """, (pedido_id,))
                productos = cursor.fetchall()

                # Calcular total basado en los productos
                total_calculado = sum(p['cantidad_producto_pedido'] * p['precio_producto_pedido'] for p in productos)

        # Estructurar el pedido con sus productos
        pedidos = []
        if pedido:
            pedidos.append({
                'pedido_id': pedido['id'],
                'codigo_pedido': pedido['codigo_pedido'],
                'total_pago_pedido': total_calculado,  # Se usa el total calculado
                'fecha_ingreso_pedido': pedido['fecha_ingreso_pedido'],
                'hora_pedido': pedido['hora_pedido'],
                'estado_pedido': pedido['estado_pedido'],
                'productos': productos
            })

        return render_template('carrito.html', categorias=categorias_dict, pedidos=pedidos)

    except Exception as e:
        print(f"❌ Error al obtener el carrito: {e}")
        return "Error al cargar el carrito. Inténtelo de nuevo más tarde.", 500

    finally:
        connection.close()

@app.route('/config')
def config():
    connection = get_db_connection()
    credencial_id = session.get("credencial")  # Obtener la credencial desde la sesión

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener credencial
            cursor.execute("SELECT * FROM credencial WHERE id = %s", (credencial_id,))
            credencial = cursor.fetchone()

            # Obtener productos recientes
            cursor.execute("""
                SELECT a.id, a.nombre, a.cod, a.descripcion, a.unidadVenta, a.precioVenta, a.fechaAlta,
                (SELECT i.imagen 
                FROM modelo i 
                WHERE i.articulo = a.id 
                ORDER BY i.id ASC 
                LIMIT 1) AS imagen_url
                FROM articulo a
                ORDER BY a.id DESC LIMIT 5;
            """)
            productos = cursor.fetchall()

            # Obtener registros de backup de precios
            cursor.execute("""
                SELECT b.id, b.idBorrado, b.motivo, b.usuario, 
                       b.nombreUser, b.mailUser, b.credencial, b.fechaCambio, b.categoria, b.accion
                FROM backupprecioventa b
                ORDER BY b.id DESC LIMIT 5;
            """)
            datos_backupprecioventa = cursor.fetchall()

            # Obtener pedidos recientes
            cursor.execute("""
                SELECT g.id AS pedido_id, g.cod AS codigo_pedido, g.fechaIngreso, g.hora, 
                       g.totalPago AS precio_total_neto, g.estadoPedido, g.estadoAtencion, 
                       c.nombre AS cliente_nombre, c.apellido AS cliente_apellido, c.telefono
                FROM guiapedido g
                JOIN cliente c ON g.cliente_id = c.id
                ORDER BY g.id DESC LIMIT 5;
            """)
            pedidos = cursor.fetchall()

        return render_template('config.html', credencial=credencial, productos=productos, 
                               datos_backupprecioventa=datos_backupprecioventa, pedidos=pedidos)

    except Exception as e:
        print(f"❌ Error al obtener los datos: {e}")
        return "Error al cargar la configuración. Inténtelo de nuevo más tarde.", 500

    finally:
        connection.close()

@app.route('/gestionar_credenciales')
def gestionar_credenciales():
    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM credencial")
            credenciales = cursor.fetchall()
        return render_template('credenciales.html', credenciales=credenciales)
    except Exception as e:
        return render_template('credenciales.html', credenciales=[], error=str(e))
    finally:
        connection.close()

@app.route('/crear_credencial', methods=['POST'])
def crear_credencial():
    from flask import request, redirect, url_for
    import bcrypt

    nombre = request.form.get("nombre")
    color = request.form.get("color")
    password = request.form.get("password")

    permisos = {permiso: request.form.get(permiso) is not None for permiso in [
        "usuarios", "permisos", "banners", "categorias", "promociones", "historial",
        "productos", "ventasRealizadas", "prodMasVendidos", "pedidos"
    ]}

    if not nombre or not password:
        return redirect(url_for('gestionar_credenciales', error="Nombre y contraseña son obligatorios."))

    try:
        # Encriptar la contraseña
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO credencial (nombre, color, password, usuarios, permisos, banners, 
                                        categorias, promociones, historial, ventasRealizadas, 
                                        prodMasVendidos, productos, pedidos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre, color, hashed_password, *permisos.values()))
            connection.commit()

        return redirect(url_for('gestionar_credenciales'))
    except Exception as e:
        return redirect(url_for('gestionar_credenciales', error=str(e)))
    finally:
        connection.close()


@app.route('/editar_credencial/<int:id>', methods=['POST'])
def editar_credencial(id):
    from flask import request, redirect, url_for
    import bcrypt

    password = request.form.get("password")

    # Obtener permisos y asegurarse de que sean valores 0 o 1
    permisos = {
        "usuarios": 1 if request.form.get("usuarios") else 0,
        "permisos": 1 if request.form.get("permisos") else 0,
        "banners": 1 if request.form.get("banners") else 0,
        "categorias": 1 if request.form.get("categorias") else 0,
        "promociones": 1 if request.form.get("promociones") else 0,
        "historial": 1 if request.form.get("historial") else 0,
        "ventasRealizadas": 1 if request.form.get("ventasRealizadas") else 0,
        "prodMasVendidos": 1 if request.form.get("prodMasVendidos") else 0,
        "productos": 1 if request.form.get("productos") else 0,
        "pedidos": 1 if request.form.get("pedidos") else 0
    }

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Si el usuario ingresó una nueva contraseña, la encriptamos
            if password:
                salt = bcrypt.gensalt()
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                
                cursor.execute("""
                    UPDATE credencial 
                    SET password = %s, usuarios = %s, permisos = %s, banners = %s, categorias = %s, 
                        promociones = %s, historial = %s, ventasRealizadas = %s, prodMasVendidos = %s, 
                        productos = %s, pedidos = %s
                    WHERE id = %s
                """, (hashed_password, permisos["usuarios"], permisos["permisos"], permisos["banners"], 
                      permisos["categorias"], permisos["promociones"], permisos["historial"], 
                      permisos["ventasRealizadas"], permisos["prodMasVendidos"], permisos["productos"], 
                      permisos["pedidos"], id))
            else:
                # Si no se ingresa una nueva contraseña, solo actualizamos los permisos
                cursor.execute("""
                    UPDATE credencial 
                    SET usuarios = %s, permisos = %s, banners = %s, categorias = %s, 
                        promociones = %s, historial = %s, ventasRealizadas = %s, prodMasVendidos = %s, 
                        productos = %s, pedidos = %s
                    WHERE id = %s
                """, (permisos["usuarios"], permisos["permisos"], permisos["banners"], 
                      permisos["categorias"], permisos["promociones"], permisos["historial"], 
                      permisos["ventasRealizadas"], permisos["prodMasVendidos"], permisos["productos"], 
                      permisos["pedidos"], id))
            
            connection.commit()

        return redirect(url_for('gestionar_credenciales', mensaje="Credencial actualizada correctamente."))
    except Exception as e:
        return redirect(url_for('gestionar_credenciales', error=f"Error al actualizar: {e}"))
    finally:
        connection.close()

@app.route('/usuarios')
def usuarios():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT empleados.id, empleados.nombre, empleados.apellido, empleados.email, empleados.telefono, 
                       credencial.nombre AS rol, credencial.password 
                FROM empleados 
                JOIN credencial ON empleados.id_credencial = credencial.id
            """)
            empleados = cursor.fetchall()
            print("Los usuarios existentes son: ", empleados)  # Solo para depuración

        # Devuelve la plantilla con los datos de los empleados
        return render_template('usuarios.html', empleados=empleados)
    
    except Exception as e:
        # En caso de error, muestra una página de error con el mensaje
        return render_template('usuarios.html', empleados=[], error=str(e))
    
    finally:
        # Asegúrate de cerrar la conexión a la base de datos
        if connection:
            connection.close()

@app.route('/actualizar_empleados', methods=['POST'])
def actualizar_empleados():
    try:
        # Establecer la conexión a la base de datos PostgreSQL
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Iterar sobre los empleados que han sido actualizados
            for key, value in request.form.items():
                if key.startswith("id_"):  # Verificar que la clave es de un empleado
                    empleado_id = value
                    nombre = request.form.get(f"nombre_{empleado_id}")
                    apellido = request.form.get(f"apellido_{empleado_id}")
                    email = request.form.get(f"email_{empleado_id}")
                    telefono = request.form.get(f"telefono_{empleado_id}")
                    credencial_nombre = request.form.get(f"rol_{empleado_id}")  # Obtener el nombre de la credencial

                    # Verificar que los datos esenciales no estén vacíos
                    if not nombre or not apellido or not email or not telefono or not credencial_nombre:
                        flash(f"Todos los campos deben ser llenados para el empleado con ID {empleado_id}", 'error')
                        continue

                    # Obtener el ID de la credencial a partir de su nombre
                    cursor.execute("SELECT id FROM credencial WHERE nombre = %s", (credencial_nombre,))
                    credencial_id = cursor.fetchone()

                    if credencial_id:
                        credencial_id = credencial_id[0]  # Extraer el valor real del ID

                        # Actualizar los datos del empleado con la credencial asociada
                        cursor.execute("""
                            UPDATE empleados 
                            SET nombre = %s, apellido = %s, email = %s, telefono = %s, id_credencial = %s
                            WHERE id = %s
                        """, (nombre, apellido, email, telefono, credencial_id, empleado_id))
                    else:
                        flash(f"Credencial '{credencial_nombre}' no encontrada para el empleado con ID {empleado_id}", 'error')

        connection.commit()  # Confirmar los cambios realizados
        flash('Datos actualizados correctamente.', 'success')  # Mensaje de éxito
        return redirect(url_for('usuarios'))  # Redirigir a la página de usuarios después de actualizar
    except Exception as e:
        connection.rollback()  # Revertir en caso de error
        flash(f"Error al actualizar los empleados: {str(e)}", 'error')  # Mensaje de error
        return redirect(url_for('usuarios'))  # Redirigir a la página de usuarios en caso de error
    finally:
        if connection:
            connection.close()  # Cerrar la conexión

@app.route('/productosConfig', methods=['GET', 'POST'])
def productosConfig():
    connection = get_db_connection()

    # Obtener todos los productos existentes
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT a.id, a.nombre, a.cod, a.descripcion, a.unidadVenta, a.precioVenta, a.fechaAlta,
            (SELECT i.imagen 
            FROM modelo i 
            WHERE i.articulo = a.id 
            ORDER BY i.id ASC 
            LIMIT 1) AS imagen_url
            FROM articulo a
            ORDER BY a.id DESC;
        """)
        productos = cursor.fetchall()  # Lista de productos

    # Obtener todas las categorías existentes
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM clasearticulo ORDER BY nombre ASC")
        categorias = cursor.fetchall()  # Lista de categorías

    # Obtener todas las subcategorías
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT subClase.*, clasearticulo.nombre AS categoria_nombre 
            FROM subClase 
            JOIN clasearticulo ON subClase.claseArticulo = clasearticulo.id 
            ORDER BY categoria_nombre ASC;
        """)
        subCat = cursor.fetchall()  # Lista de subcategorías

    if request.method == 'POST':
        nombre_producto = request.form.get('nombreProducto')
        codigo_producto = request.form.get('codigoProducto', '')
        imagen = request.files.get('imagenProducto')
        descripcion_producto = request.form.get('descripcionProducto')
        origen_producto = request.form.get('origenProducto', 'China')
        clase = request.form.get('categoriaSub')
        precio_producto = request.form.get('precioProducto')
        unidad_venta = request.form.get('unidadVenta', 'Unidad')
        fecha_alta = request.form.get('fechaAlta')

        # Validar los campos requeridos
        if not nombre_producto or not descripcion_producto or not clase or not precio_producto:
            flash('Todos los campos obligatorios deben estar llenos', 'error')
            return redirect(url_for('productosConfig'))

        # Subir la imagen si existe y es válida
        if imagen and allowed_file(imagen.filename):
            imagen_filename = secure_filename(imagen.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
            imagen.save(imagen_path)
            imagen_url = url_for('static', filename='uploads/' + imagen_filename)
        else:
            imagen_url = None

        # Insertar el nuevo producto en la base de datos
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO articulo (nombre, cod, img, descripcion, origen, idClaseArticulo, precioVenta, unidadVenta, fechaAlta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre_producto, codigo_producto, imagen_url, descripcion_producto, origen_producto, clase, precio_producto, unidad_venta, fecha_alta))
            connection.commit()

        flash('Producto agregado exitosamente', 'success')
        return redirect(url_for('productosConfig'))  # Redirigir a la misma página para ver el cambio

    connection.close()
    return render_template('productosConfig.html', productos=productos, categorias=categorias, subCat=subCat)

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    try:
        # Obtener datos del formulario
        nombre = request.form['nombreProducto']
        codigo = request.form['codigoProducto']
        descripcion = request.form['descripcionProducto']
        origen = request.form['origenProducto']
        clase = request.form['categoriaSub']
        precio = request.form['precioProducto']
        stock = request.form['unidadVenta']  # Ahora el stock se guardará en modelo
        fecha_alta = request.form['fechaAlta']
        nombre_modelo = request.form['modeloProducto']
        imagen = request.files['imagenProducto']
        categoria = request.form['categoria']
        accion = request.form['accion']
        categoriaM = request.form['categoriaM']
        accioncM = request.form['accionM']
        
        motivo = f"Se creó el producto: {nombre} de Precio: {precio}"
        motivo_modelo = f"Se creó el modelo: {nombre_modelo}"

        # Validar imagen
        if imagen and allowed_file(imagen.filename):
            imagen_filename = secure_filename(imagen.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
            imagen.save(imagen_path)
            imagen_url = url_for('static', filename=f'uploads/{imagen_filename}')

            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    # Insertar el nuevo producto en la tabla `articulo`
                    cursor.execute("""
                        INSERT INTO articulo (nombre, cod, descripcion, origen, idClaseArticulo, precioVenta, fechaAlta)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (nombre, codigo, descripcion, origen, clase, precio, fecha_alta))

                    # Obtener el ID del artículo recién insertado
                    cursor.execute("SELECT LASTVAL()")
                    id_articulo = cursor.fetchone()[0]

                    # Insertar el backup para el producto
                    insertar_backup(connection, id_articulo, motivo, categoria, accion, usuario=None, nombreUser=None, mailUser=None, fechaCambio=None, credencial=None)

                    # Insertar el modelo en la tabla `modelo` con el stock
                    cursor.execute("""
                        INSERT INTO modelo (nombre, imagen, stock, articulo)
                        VALUES (%s, %s, %s, %s)
                    """, (nombre_modelo, imagen_url, stock, id_articulo))

                    # Obtener el ID del modelo recién insertado
                    cursor.execute("SELECT LASTVAL()")
                    id_modelo = cursor.fetchone()[0]

                    # Insertar el backup para el modelo
                    insertar_backup(connection, id_modelo, motivo_modelo, categoriaM, accioncM, usuario=None, nombreUser=None, mailUser=None, fechaCambio=None, credencial=None)

                    # Confirmar la transacción
                    connection.commit()

                flash('Producto agregado exitosamente', 'success')
                
            except Exception as e:
                connection.rollback()
                print("Error en agregar_producto:", e)
                flash('Error al agregar el producto.', 'error')
            finally:
                connection.close()
        else:
            flash('Por favor, suba un archivo de imagen válido', 'error')

    except Exception as e:
        print("Error en agregar_producto:", e)
        flash('Error al agregar el producto.', 'error')

    # Redirigir SIEMPRE a productosConfig después de agregar un producto
    return redirect(url_for('productosConfig'))

@app.route('/historial')
def historial():
    if not verificar_permiso("historial"):
        return redirect(url_for('password'))

    connection = get_db_connection()
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, idborrado, motivo, categoria, accion, fechacambio, usuario, nombreuser, mailuser, credencial
            FROM backupprecioventa
            ORDER BY id DESC;
        """)
        # Obtén los datos del historial (en formato de diccionario)
        datos_backupprecioventa = cursor.fetchall()
    
    connection.close()
    
    return render_template('historial.html', datos_backupprecioventa=datos_backupprecioventa)

@app.route('/eliminar_producto/<int:producto_id>', methods=['GET', 'POST'])
def eliminar_producto(producto_id):
    try:
        # Conexión a la base de datos
        connection = get_db_connection()
        cursor = connection.cursor()

        # Obtener los datos del producto antes de eliminarlo
        cursor.execute("SELECT * FROM articulo WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()

        if not producto:
            flash('El producto no existe.', 'error')
            return redirect(url_for('productosConfig'))

        if request.method == 'POST':
            # Obtener el motivo del formulario
            motivo = request.form['motivo']
            nombre = request.form['nombre']
            categoria = request.form['categoria']
            accion = request.form['accion']

            motivo = f"Se elimino el producto: {nombre} por la siguiente Razón: {motivo}"

            # Eliminar el producto de la tabla 'articulo' y 'modelo'
            cursor.execute("DELETE FROM modelo WHERE articulo_id = %s", (producto_id,))
            cursor.execute("DELETE FROM articulo WHERE id = %s", (producto_id,))
            connection.commit()

            # Insertar respaldo de la acción de eliminación
            insertar_backup(connection, producto_id, motivo, categoria, accion, usuario=None, nombreUser=None, mailUser=None, fechaCambio=None, credencial=None)

            flash('Producto eliminado exitosamente y respaldo de precio creado.', 'success')
            return redirect(url_for('modelos', id=producto_id))

        return render_template('productosConfig.html', producto_id=producto_id, producto=producto)

    except Exception as e:
        connection.rollback()
        flash(f"Error al eliminar el producto: {str(e)}", 'error')

    finally:
        cursor.close()  # Cierra el cursor solo al final
        connection.close()  # Asegura que la conexión se cierre correctamente

@app.route('/actualizar_stock/<int:modelo_id>', methods=['POST'])
def actualizar_stock(modelo_id):
    data = request.get_json()
    nuevo_stock = data.get("stock")

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Actualizamos el stock en la tabla 'modelo' de PostgreSQL
            cursor.execute("UPDATE modelo SET stock = %s WHERE id = %s", (nuevo_stock, modelo_id))
            connection.commit()

            return jsonify({"success": True})
    except Exception as e:
        print("Error al actualizar stock:", e)
        return jsonify({"success": False}), 500
    finally:
        connection.close()

@app.route('/eliminar_modelo/<int:modelo_id>', methods=['POST'])
def eliminar_modelo(modelo_id):
    # Obtener correctamente los valores del formulario
    id_producto = request.form.get('idProducto')  # ID del producto al que pertenece el modelo
    categoria = request.form['categoria']
    accion = request.form['accion']
    nombre = request.form['nombre']
    motivo = request.form['motivo']

    motivo_modelo = f"Se eliminó el modelo: {nombre} por la siguiente razón: {motivo}"

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            # Eliminar el modelo de la tabla 'modelo'
            cursor.execute("DELETE FROM modelo WHERE id = %s", (modelo_id,))
            
            # Insertar en la tabla de respaldo (asumiendo que insertar_backup es una función previamente definida)
            insertar_backup(connection, modelo_id, motivo_modelo, categoria, accion, usuario=None, nombreUser=None, mailUser=None, fechaCambio=None, credencial=None)

            # Confirmar la transacción
            connection.commit()

            # Flash para confirmar que el modelo fue eliminado
            flash('Modelo eliminado exitosamente.', 'success')

    except Exception as e:
        # En caso de error, se revierte la transacción
        connection.rollback()
        flash(f'Error al eliminar el modelo: {str(e)}', 'error')

    finally:
        # Cerrar la conexión
        connection.close()

    # Redirigir a la vista de modelos con el ID del producto
    return redirect(url_for('modelos', id=id_producto))

@app.route('/editar_producto', methods=['POST'])
def editar_producto():
    # Obtener los datos del formulario
    id_producto = request.form.get('id')
    nombre = request.form.get('nombre')
    codigo = request.form.get('codigo')
    descripcion = request.form.get('descripcion')
    precio_venta = request.form.get('precioVenta')
    motivo = request.form.get('motivoCambio', '')  # Valor predeterminado en caso de que no se proporcione
    accion = request.form.get('accion', 'Edicion')  # Valor por defecto en caso de no existir
    categoria = request.form.get('categoria', 'Producto')  # Valor por defecto si falta

    # Crear el motivo para el respaldo
    motivo_modelo = f"Se modificó el modelo: {nombre} por la razón: {motivo}. Ahora sus valores son -> Código: {codigo}, Precio: {precio_venta}, Descripción: {descripcion}"

    connection = get_db_connection()
    
    if not connection:
        flash('Error al conectar con la base de datos.', 'error')
        return redirect(url_for('productosConfig'))

    try:
        with connection.cursor() as cursor:
            # Realizar la actualización del producto
            cursor.execute("""
                UPDATE articulo
                SET nombre = %s, cod = %s, descripcion = %s, precioVenta = %s
                WHERE id = %s
            """, (nombre, codigo, descripcion, precio_venta, id_producto))

            # Insertar un respaldo sobre la modificación
            insertar_backup(connection, id_producto, motivo_modelo, categoria, accion)

        connection.commit()  # Confirmar la transacción
        flash('Producto actualizado y respaldo de cambios realizado.', 'success')
    except Exception as e:
        connection.rollback()  # En caso de error, deshacer cambios
        print(f"Error en editar_producto: {e}")
        flash(f'Error al editar el producto: {e}', 'error')
    finally:
        connection.close()  # Asegurarse de cerrar la conexión

    return redirect(url_for('modelos', id=id_producto))

@app.route('/modelos')
def modelos():
    producto_id = request.args.get('id', type=int) or request.args.get('producto_id', type=int)

    if not producto_id:
        flash("Producto no encontrado", "error")
        return render_template('modelos.html', producto=None, modelos=[])

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Obtener el producto por su ID
            cursor.execute("""
                SELECT id, nombre, cod, descripcion, precioVenta
                FROM articulo
                WHERE id = %s
            """, (producto_id,))
            producto = cursor.fetchone()

            # Verificar si el producto existe
            if not producto:
                flash("Producto no encontrado", "error")
                return render_template('modelos.html', producto=None, modelos=[])

            # Obtener los modelos asociados al producto
            cursor.execute("""
                SELECT id, nombre, imagen, stock
                FROM modelo
                WHERE articulo = %s
            """, (producto_id,))
            modelos = cursor.fetchall()  # Obtener todos los modelos

        print(f"Producto obtenido: {producto}")
        print(f"Modelos obtenidos: {modelos}")

    except Exception as e:
        print("Error en modelos:", e)
        flash(f"Error al obtener los modelos: {str(e)}", 'error')
        producto = None
        modelos = []  # Si hay un error, enviar una lista vacía

    finally:
        connection.close()

    return render_template('modelos.html', producto=producto, modelos=modelos)

@app.route('/agregar_modelo', methods=['POST'])
def agregar_modelo():
    try:
        id_producto = request.form['idProducto']
        nombre_modelo = request.form['nombreProducto']
        imagen = request.files['imagenProducto']
        stock = request.form['unidadVenta']
        accion = request.form['accion']
        categoria = request.form['categoria']

        motivo_modelo = f"Se creó el modelo: {nombre_modelo}"

        print('ID del producto:', id_producto)

        # Verificar que la imagen esté en el formato adecuado
        if imagen and allowed_file(imagen.filename):
            imagen_filename = secure_filename(imagen.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
            imagen.save(imagen_path)
            imagen_url = url_for('static', filename=f'uploads/{imagen_filename}')

            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    # Realizamos la inserción del modelo en PostgreSQL
                    cursor.execute("""
                        INSERT INTO modelo (nombre, imagen, stock, articulo) 
                        VALUES (%s, %s, %s, %s) RETURNING id
                    """, (nombre_modelo, imagen_url, stock, id_producto))

                    # Obtener el ID del nuevo modelo insertado
                    id_modelo = cursor.fetchone()[0]  # fetchone() devuelve una tupla

                    connection.commit()

                    # Llamamos a la función de backup (sin cambios)
                    insertar_backup(connection, id_modelo, motivo_modelo, categoria, accion)

                flash('Modelo agregado exitosamente', 'success')

            except Exception as e:
                connection.rollback()
                print("Error en agregar_modelo:", e)
                flash('Error al agregar el modelo.', 'error')

            finally:
                connection.close()
        else:
            flash('Por favor, suba un archivo de imagen válido', 'error')

    except Exception as e:
        print("Error en agregar_modelo:", e)
        flash('Error al agregar el modelo.', 'error')

    return redirect(url_for('modelos', id=id_producto))  # Redirigir con el ID del producto

@app.route('/agregar_categoria', methods=['POST'])
def agregar_categoria():
    if request.method == 'POST':
        # Obtener el nombre de la categoría desde el formulario
        categoria_nombre = request.form['categoriaNombre']
        accion = request.form['accionC']
        categoria = request.form['categoriaC']

        motivo_categoria = f"Se creó la categoria: {categoria_nombre}"
        
        # Establecer la conexión a la base de datos
        connection = get_db_connection()

        # Insertar la nueva categoría en la base de datos
        try:
            with connection.cursor() as cursor:
                # Insertar la nueva categoría en la tabla clasearticulo
                cursor.execute("INSERT INTO clasearticulo (nombre) VALUES (%s) RETURNING id", (categoria_nombre,))
                
                # Obtener el id de la categoría recién insertada
                id_categoria = cursor.fetchone()[0]  # fetchone() devuelve una tupla con el valor del id

                connection.commit()

                # Llamada a la función para insertar un backup (sin cambios en la llamada)
                insertar_backup(connection, id_categoria, motivo_categoria, categoria, accion)

            flash('Categoría agregada exitosamente', 'success')
        except Exception as e:
            connection.rollback()
            flash(f'Error al agregar la categoría: {str(e)}', 'error')
        finally:
            connection.close()

        return redirect(url_for('productosConfig'))  # Redirigir a la página de configuración para mostrar el cambio

@app.route('/agregar_subCategoria', methods=['POST'])
def agregar_subCategoria():
    if request.method == 'POST':
        # Obtener el nombre de la subcategoría desde el formulario
        subcategoria_nombre = request.form['subCat']
        categoria = request.form['categoriaSub']

        accion = request.form['accionSC']
        categoriaC = request.form['categoriaSC']

        motivo_categoria = f"Se creó la SUB categoría: {subcategoria_nombre}"
        
        # Establecer la conexión a la base de datos
        connection = get_db_connection()

        # Insertar la nueva subcategoría en la base de datos
        try:
            with connection.cursor() as cursor:
                # Insertar la nueva subcategoría en la tabla subClase
                cursor.execute("INSERT INTO subClase (nombre, claseArticulo) VALUES (%s, %s) RETURNING id", 
                               (subcategoria_nombre, categoria))

                # Obtener el ID de la subcategoría recién insertada
                id_subCategoria = cursor.fetchone()[0]  # fetchone() devuelve una tupla con el valor del id

                connection.commit()

                # Llamada a la función para insertar un backup (sin cambios en la llamada)
                insertar_backup(connection, id_subCategoria, motivo_categoria, categoriaC, accion)

            flash('Sub Categoría agregada exitosamente', 'success')
        except Exception as e:
            connection.rollback()
            flash(f'Error al agregar la subcategoría: {str(e)}', 'error')
        finally:
            connection.close()

        return redirect(url_for('productosConfig'))  # Redirigir a la página de configuración para mostrar el cambio

@app.route('/get_product/<int:product_id>/<int:model_id>', methods=['GET'])
def get_product(product_id, model_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT 
                a.nombre AS articulo_nombre, 
                a.cod, 
                a.descripcion, 
                a.precioVenta, 
                m.nombre AS modelo_nombre, 
                m.imagen 
            FROM 
                articulo a 
            JOIN 
                modelo m ON a.id = m.articulo 
            WHERE 
                a.id = %s AND m.id = %s
            """
            # Ejecución de la consulta con los parámetros proporcionados
            cursor.execute(sql, (product_id, model_id))
            result = cursor.fetchone()  # Obtener una fila del resultado
            
            if result:
                # Si se encuentra el producto y el modelo, construir el diccionario
                product = {
                    "articulo_nombre": result[0],
                    "cod": result[1],
                    "descripcion": result[2],
                    "precioVenta": str(result[3]),  # Convertir a string si es necesario
                    "modelo_nombre": result[4],
                    "imagen": result[5]
                }
                return jsonify(product)  # Retornar los detalles del producto como JSON
            else:
                # Si no se encuentra el producto o modelo, retornar error 404
                return jsonify({"error": "Producto o modelo no encontrado"}), 404
    except Exception as e:
        # Si ocurre un error en la base de datos o en el procesamiento
        return jsonify({"error": str(e)}), 500
    finally:
        # Asegurarse de cerrar la conexión después de la operación
        connection.close()

@app.route('/agregarPedido', methods=['GET', 'POST'])
def agregarPedido():
    if request.method == 'POST':
        producto_id = request.form.get('producto_id')
        modelo_id = request.form.get('modelo_id')
        cantidad = int(request.form.get('cantidad', 1))  # Cantidad seleccionada por el usuario

        cliente_id = request.cookies.get('cliente_id')

        if not cliente_id:
            return redirect(url_for('index'))  # Si no hay cliente, recargar página para generar uno

        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:
                # Verificar si el cliente ya tiene un pedido activo
                cursor.execute("""
                    SELECT id FROM guiapedido 
                    WHERE cliente_id = %s AND estadoPedido = 'pendiente'
                    LIMIT 1;
                """, (cliente_id,))
                pedido = cursor.fetchone()

                if not pedido:
                    # Si no hay pedido, crearlo
                    cod_pedido = str(uuid.uuid4())[:9]
                    cursor.execute("""
                        INSERT INTO guiapedido (cod, fechaIngreso, hora, cliente_id, totalPago, estadoPedido, estadoAtencion, mediopago) 
                        VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, 0.00, 'pendiente', 'P', NULL)
                    """, (cod_pedido, cliente_id))
                    connection.commit()
                    pedido_id = cursor.lastrowid  # Obtener el ID del pedido recién creado
                else:
                    pedido_id = pedido['id']

            with connection.cursor() as cursor:
                # Verificar si el producto ya está en el pedido
                cursor.execute("""
                    SELECT cantidad FROM productopedido 
                    WHERE pedidoId = %s AND codProducto = %s;
                """, (pedido_id, modelo_id))
                producto_existente = cursor.fetchone()

                if producto_existente:
                    # Si el producto ya existe, actualizar la cantidad sumando la nueva cantidad
                    nueva_cantidad = producto_existente['cantidad'] + cantidad
                    cursor.execute("""
                        UPDATE productopedido 
                        SET cantidad = %s 
                        WHERE pedidoId = %s AND codProducto = %s;
                    """, (nueva_cantidad, pedido_id, modelo_id))
                else:
                    # Si no existe, insertarlo como nuevo
                    cursor.execute("""
                        INSERT INTO productopedido (pedidoId, codProducto, nombreProducto, precio, cantidad)
                        SELECT %s, m.id, a.nombre, a.precioVenta, %s
                        FROM modelo m
                        JOIN articulo a ON m.articulo = a.id
                        WHERE m.id = %s;
                    """, (pedido_id, cantidad, modelo_id))
                
                connection.commit()

        except Exception as e:
            connection.rollback()
            flash(f'Error al procesar el pedido: {str(e)}', 'error')
        finally:
            connection.close()

        return redirect(url_for('producto', id=producto_id))

    else:
        producto_id = request.args.get('producto_id')
        modelo_id = request.args.get('modelo_id')

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Consultar el nombre del producto
                cursor.execute("SELECT nombre FROM articulo WHERE id = %s", (producto_id,))
                producto = cursor.fetchone()
                producto_nombre = producto['nombre'] if producto else 'Producto Desconocido'

                # Consultar el nombre del modelo
                cursor.execute("SELECT nombre FROM modelo WHERE id = %s", (modelo_id,))
                modelo = cursor.fetchone()
                modelo_nombre = modelo['nombre'] if modelo else 'Modelo Desconocido'

        finally:
            connection.close()

        return render_template('agregarProducto.html', 
                               producto_nombre=producto_nombre, 
                               modelo_nombre=modelo_nombre, 
                               producto_id=producto_id)

@app.route('/pedidos')
def pedidos():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Consultar todos los pedidos con información del cliente
        cursor.execute("""
            SELECT 
                g.id AS pedido_id, 
                g.cod AS codigo_pedido, 
                g.fechaIngreso, 
                g.hora, 
                g.totalPago AS precio_total_neto, 
                g.estadoPedido, 
                g.estadoAtencion, 
                g.mediopago,
                c.nombre AS cliente_nombre, 
                c.apellido AS cliente_apellido, 
                c.cuitDni AS cliente_cuitDni, 
                c.direccion AS cliente_direccion, 
                c.localidad AS cliente_localidad, 
                c.provincia AS cliente_provincia, 
                c.telefono AS cliente_telefono, 
                c.email AS cliente_email, 
                c.id AS cliente_id
            FROM 
                guiapedido g
            JOIN 
                cliente c ON g.cliente_id = c.id
            ORDER BY 
                g.id DESC;
        """)
        pedidos = cursor.fetchall()

        # Depuración: imprimir los datos de los pedidos y clientes
        for pedido in pedidos:
            print(f"Pedido ID: {pedido['pedido_id']}")
            print(f"  Cliente Nombre: {pedido['cliente_nombre']}")
            print(f"  Cliente Apellido: {pedido['cliente_apellido']}")
            cursor.execute("""
                SELECT pp.id, pp.codProducto AS producto_id, pp.nombreProducto, pp.precio, pp.cantidad, m.imagen
                FROM productopedido pp
                JOIN modelo m ON pp.codProducto = m.id
                WHERE pp.pedidoId = %s;
            """, (pedido["pedido_id"],))
            pedido["productos"] = cursor.fetchall()

            # Depuración: Imprimir los productos del pedido
            print(f"Pedido ID: {pedido['pedido_id']}")
            for producto in pedido["productos"]:
                print(f"  Producto ID: {producto['producto_id']}, Nombre: {producto['nombreProducto']}")

    except Exception as e:
        print("Error al obtener pedidos:", e)
        pedidos = []

    finally:
        cursor.close()
        connection.close()

    return render_template('pedidos.html', pedidos=pedidos)

@app.route('/editar_pedido/<int:pedido_id>', methods=['POST'])
def editar_pedido(pedido_id):
    try:
        data = request.json
        nuevo_estado = data.get("estado")
        
        # Establecer la conexión a PostgreSQL
        connection = get_db_connection()

        with connection.cursor() as cursor:
            # Actualizar el estado del pedido en la base de datos
            cursor.execute("UPDATE guiapedido SET estadoPedido = %s WHERE id = %s", (nuevo_estado, pedido_id))
        
        # Confirmar los cambios en la base de datos
        connection.commit()
        return jsonify({"mensaje": "Pedido actualizado correctamente"})
    
    except Exception as e:
        # Manejo de errores en caso de que algo falle
        return jsonify({"error": str(e)})
    
    finally:
        # Cerrar la conexión a la base de datos
        connection.close()

@app.route('/eliminar_pedido/<int:pedido_id>', methods=['POST'])
def eliminar_pedido(pedido_id):
    try:
        # Establecer la conexión a PostgreSQL
        connection = get_db_connection()

        # Crear un cursor para ejecutar la consulta
        with connection.cursor() as cursor:
            # Ejecutar la consulta DELETE para eliminar el pedido
            cursor.execute("DELETE FROM guiapedido WHERE id = %s", (pedido_id,))
        
        # Confirmar los cambios en la base de datos
        connection.commit()
        
        # Redirigir al usuario a la página principal (index)
        return redirect(url_for('index'))
    
    except Exception as e:
        # Manejo de errores en caso de que algo falle
        return jsonify({"error": str(e)})

    finally:
        # Cerrar la conexión a la base de datos
        connection.close()

@app.route('/procesar_pedido', methods=['POST'])
def procesar_pedido():
    telefono = "+54 9 11 1234-5678"
    banco = "Banco Ficticio"
    alias_cuenta = "alias.falso.123"
    cbu = "2850590940090418135201"
    data = request.json  
    cliente_id = request.cookies.get('cliente_id')

    if not cliente_id:
        return jsonify({"success": False, "message": "No se encontró el ID del cliente."})

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        # 🔹 **Actualizar los datos del cliente**
        cursor.execute("SELECT id FROM cliente WHERE id = %s", (cliente_id,))
        cliente = cursor.fetchone()

        if not cliente:
            return jsonify({"success": False, "message": "Cliente no encontrado."})

        cursor.execute("""
            UPDATE cliente 
            SET nombre = %s, apellido = %s, cuit_dni = %s, direccion = %s, 
                localidad = %s, provincia = %s, telefono = %s, email = %s
            WHERE id = %s
        """, (data['nombre'], data['apellido'], data['dni'], data['direccion'], 
              data['localidad'], data['provincia'], data['telefono'], data['email'], cliente_id))
        connection.commit()

        # 🔹 **Obtener el pedido pendiente**
        cursor.execute("""
            SELECT id FROM guiapedido 
            WHERE cliente_id = %s AND estado_pedido = 'pendiente'
            LIMIT 1;
        """, (cliente_id,))
        pedido = cursor.fetchone()

        if not pedido:
            return jsonify({"success": False, "message": "No se encontró un pedido pendiente."})

        pedido_id = pedido['id']

        # 🔹 **Obtener los productos del pedido**
        cursor.execute("""
            SELECT pp.cod_producto, pp.cantidad, pp.precio, m.nombre AS modelo_nombre, 
                   p.nombre AS articulo_nombre, m.stock 
            FROM productopedido pp
            JOIN modelo m ON pp.cod_producto = m.id
            JOIN articulo p ON m.articulo = p.id
            WHERE pp.pedido_id = %s;
        """, (pedido_id,))
        productos = cursor.fetchall()

        # 🔹 **Actualizar stock y validar cantidades**
        for producto in productos:
            producto_id = producto['cod_producto']
            cantidad_pedida = producto['cantidad']
            stock_actual = producto['stock']

            if stock_actual < cantidad_pedida:
                return jsonify({"success": False, "message": f"Stock insuficiente para el producto {producto['articulo_nombre']} ({producto['modelo_nombre']})."})

            # 🔹 Restar del stock en `modelo`
            nuevo_stock = stock_actual - cantidad_pedida
            cursor.execute("""
                UPDATE modelo 
                SET stock = %s 
                WHERE id = %s;
            """, (nuevo_stock, producto_id))
            connection.commit()

            # 🔹 Asegurar que la cantidad pedida se actualice correctamente
            cursor.execute("""
                UPDATE productopedido 
                SET cantidad = %s 
                WHERE cod_producto = %s AND pedido_id = %s;
            """, (cantidad_pedida, producto_id, pedido_id))
            connection.commit()

        # 🔹 **Calcular y actualizar el total del pedido**
        cursor.execute("""
            SELECT SUM(pp.cantidad * pp.precio) AS total_pedido
            FROM productopedido pp
            WHERE pp.pedido_id = %s;
        """, (pedido_id,))
        total_resultado = cursor.fetchone()
        total_pedido = total_resultado['total_pedido'] if total_resultado['total_pedido'] else 0.0

        cursor.execute("""
            UPDATE guiapedido 
            SET total_pago = %s, estado_pedido = 'confirmado' 
            WHERE id = %s;
        """, (total_pedido, pedido_id))
        connection.commit()

        # 🔹 **Generar el PDF**
        pdf_folder = "static/pdf"
        if not os.path.exists(pdf_folder):
            os.makedirs(pdf_folder)

        pdf_filename = f"Comprobante.pdf"
        pdf_path = os.path.join(pdf_folder, pdf_filename)

        c = canvas.Canvas(pdf_path, pagesize=letter)
        # Encabezado del comprobante
        c.drawString(100, 770, "Comprobante de Pedido")
        c.drawString(100, 750, f"Pedido #{pedido_id}")

        # Información del cliente
        c.drawString(100, 730, f"Cliente: {data['nombre']} {data['apellido']}")
        c.drawString(100, 710, f"DNI: {data['dni']}")
        c.drawString(100, 690, f"Dirección: {data['direccion']}, {data['localidad']}, {data['provincia']}")
        c.drawString(100, 670, f"Teléfono: {data['telefono']}")
        c.drawString(100, 650, f"Email: {data['email']}")

        # Línea divisoria
        c.line(50, 640, 550, 640)

        # Productos del pedido
        y = 620
        c.drawString(100, y, "Productos:")
        y -= 20

        for producto in productos:
            c.drawString(100, y, f"{producto['cantidad']} x {producto['articulo_nombre']} ({producto['modelo_nombre']}) - ${producto['precio']} c/u")
            y -= 20

        # Línea divisoria
        c.line(50, y, 550, y)
        y -= 10

        # Información de contacto
        c.setFont("Helvetica-Bold", 10)
        c.drawString(100, y, "¿Tienes alguna duda? ¡Contáctanos!")
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawString(100, y, f"Teléfono: {data['telefono']}")
        y -= 20

        # Información de la cuenta bancaria falsa
        c.drawString(100, y, "Información de la Cuenta Bancaria:")
        y -= 20
        c.drawString(100, y, f"Banco: {banco}")
        y -= 20
        c.drawString(100, y, f"Alias: {alias_cuenta}")
        y -= 20
        c.drawString(100, y, f"CBU: {cbu}")
        y -= 20

        # Línea divisoria final
        c.line(50, y, 550, y)
        y -= 10

        # Total a pagar y despedida
        c.setFont("Helvetica-Bold", 10)
        c.drawString(100, y, f"Total a pagar: ${total_pedido}")
        y -= 20
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(100, y, "Gracias por tu compra. ¡Te esperamos nuevamente!")

        c.save()

        # 🔹 **Devolver la URL del PDF**
        return jsonify({
            "success": True, 
            "message": "Pedido confirmado correctamente.", 
            "pdf_url": f"/{pdf_path}"
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"success": False, "message": "Error en el servidor."})

    finally:
        cursor.close()
        connection.close()

@app.route("/pronto", methods=["POST"])
def pronto():
    return redirect(url_for("pronto.html"))

@app.route("/actualizar_productoP", methods=["POST"])
def actualizar_producto():
    try:
        # Imprimir todos los datos recibidos en la consola del servidor
        print("🔹 Datos recibidos:", request.form)

        # Obtener datos del formulario
        producto_id = request.form.get("producto_id")
        pedido_id = request.form.get("pedido_id")
        nueva_cantidad = request.form.get("cantidad")

        # Imprimir cada dato individualmente para depuración
        print("📌 Producto ID:", producto_id)
        print("📌 Pedido ID:", pedido_id)
        print("📌 Cantidad:", nueva_cantidad)

        # Validar que los datos sean correctos
        if not producto_id or not pedido_id or not nueva_cantidad:
            print("❌ Error: Faltan datos")
            return jsonify({"error": "Faltan datos"}), 400

        nueva_cantidad = int(nueva_cantidad)

        # Conectar a la base de datos con psycopg2
        connection = get_db_connection()
        cursor = connection.cursor()

        # Ejecutar la consulta SQL con subconsulta para verificar el producto
        query = """
        SELECT pp.id, pp.pedidoid, pp.codproducto, pp.nombreproducto, pp.precio, pp.cantidad
        FROM productopedido pp
        WHERE pp.pedidoid = %s AND pp.codproducto = %s;
        """
        cursor.execute(query, (pedido_id, producto_id))
        producto = cursor.fetchone()

        # Verificar si el producto fue encontrado
        if not producto:
            print("❌ Producto no encontrado en el pedido")
            return jsonify({"error": "Producto no encontrado en el pedido"}), 404

        # Si se encuentra, actualizar la cantidad
        update_query = """
        UPDATE productopedido
        SET cantidad = %s
        WHERE pedidoid = %s AND codproducto = %s
        """
        cursor.execute(update_query, (nueva_cantidad, pedido_id, producto_id))
        connection.commit()

        # Llamar a la función para eliminar productos con cantidad 0
        eliminar_productos_cantidad_0(cursor, connection)

        # Llamar a la función para eliminar pedidos sin productos
        eliminar_pedido_sin_productos(cursor, connection)

        # Cerrar la conexión
        cursor.close()
        connection.close()

        print("✅ Actualización exitosa")
        return redirect(url_for("pedidos"))

    except Exception as e:
        print(f"❌ Error en la actualización: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/banners', methods=['GET'])
def banners():
    try:
        connection = get_db_connection()
        with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM banners")
            banners = cursor.fetchall()

        return render_template('banners.html', banners=banners)
    except Exception as e:
        flash(f"Error al obtener los banners: {str(e)}", 'error')
        return redirect(url_for('config'))

@app.route('/datos', methods=['GET', 'POST'])
def datos():
    connection = get_db_connection()
    
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            query_select_all = """
                SELECT telefono, titular, aliasCbu, cbu FROM datos
            """
            cursor.execute(query_select_all)
            all_data = cursor.fetchall()  # Obtener todos los datos de la tabla 'datos'

    finally:
        connection.close()

    if request.method == 'POST':
        telefono = request.form['telefono']
        titular = request.form['titular']
        alias = request.form['alias']
        cbu = request.form['cbu']
        
        # Conectar nuevamente a la base de datos para eliminar los datos existentes e insertar los nuevos
        connection = get_db_connection()
        
        try:
            with connection.cursor() as cursor:
                # Eliminar todos los registros en la tabla 'datos'
                query_delete_all = "DELETE FROM datos"
                cursor.execute(query_delete_all)

                # Insertar los nuevos datos del formulario
                query_insert = """
                    INSERT INTO datos (telefono, titular, aliasCbu, cbu)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query_insert, (telefono, titular, alias, cbu))

                connection.commit()  # Confirmar los cambios

        finally:
            connection.close()

        # Después de procesar los datos, redirigir con éxito
        return render_template('datos.html', success=True, all_data=all_data)

    # Si es un GET, simplemente mostramos el formulario sin datos
    return render_template('datos.html', all_data=all_data)


if __name__ == '__main__':
    app.run(debug=True)
