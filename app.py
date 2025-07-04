import flet as ft
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import os
import bcrypt
import psycopg2 # Importação do psycopg2

# --- Credenciais do Banco de Dados PostgreSQL (Externo) ---
DB_URL = "postgresql://postgres_teste_v53a_user:jTUyYul3Yerwn6dqq2AI5lHNJM1YLR3g@dpg-d1ik3nripnbc73bu61f0-a.oregon-postgres.render.com/postgres_teste_v53a"

# --- Credenciais Padrão do Administrador ---
DEFAULT_ADMIN_USERNAME = os.environ.get("HUB_ADMIN_USER", "admin_dev")
DEFAULT_ADMIN_PASSWORD = os.environ.get("HUB_ADMIN_PASS", "dev_password")

# --- Configuração do banco de dados (Conexão PostgreSQL) ---
def get_db_connection():
    """Estabelece e retorna uma conexão com o banco de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(DB_URL)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados PostgreSQL: {e}")
        # Em um aplicativo real, você pode querer levantar uma exceção ou exibir uma mensagem de erro ao usuário.
        return None

def setup_database():
    """Cria as tabelas necessárias no banco de dados se elas não existirem."""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nome TEXT UNIQUE NOT NULL,
                    senha TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    is_viajante INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                    id SERIAL PRIMARY KEY,
                    mapa TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    data_reserva TEXT NOT NULL,
                    data_baixa TEXT,
                    campanha_id INTEGER,
                    FOREIGN KEY (campanha_id) REFERENCES campanhas(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campanhas (
                    id SERIAL PRIMARY KEY,
                    nome TEXT UNIQUE NOT NULL,
                    foto_base64 TEXT,
                    ativa INTEGER DEFAULT 0,
                    data_criacao TEXT,
                    data_finalizacao TEXT
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"Erro ao configurar o banco de dados: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

def admin_exists_in_db():
    """Verifica se o administrador padrão já existe no banco de dados."""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE nome = %s AND is_admin = 1", (DEFAULT_ADMIN_USERNAME,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        return admin is not None
    return False

def criar_admin_padrao():
    """Cria o usuário administrador padrão se ele ainda não existir."""
    if not admin_exists_in_db():
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                hashed_password = bcrypt.hashpw(DEFAULT_ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("INSERT INTO usuarios (nome, senha, is_admin) VALUES (%s, %s, 1)", (DEFAULT_ADMIN_USERNAME, hashed_password))
                conn.commit()
            except Exception as e:
                print(f"Erro ao criar admin padrão: {e}")
                conn.rollback()
            finally:
                cursor.close()
                conn.close()

# Executa o setup do banco de dados e cria o admin padrão se não existir
setup_database()
criar_admin_padrao()

# --- Dados de Territórios ---
nomes_territorios = [
    "Castro alves 1", "Castro alves 2", "jk", "Mip", "Rosendo lopes",
    "Praça saber Mariana Barbosa", "Sao Pedro 1", "Sao Pedro 2", "Sao Pedro 3",
    "Sao Pedro 4", "Beira Linha", "Pedreira Velha", "Madalena",
    "Territorio Do Comercio", "Irmã Gilma", "Duque de caxias( Marciano)",
    "Irmã Augustinha", "Irmã Marcia", "Territorio Dstak Antiga Delegacia"
]
mapas = [{"nome": f"Território N°{i+1}", "descricao": nomes_territorios[i]} for i in range(len(nomes_territorios))]

# --- Funções de Utilitário de Banco de Dados ---
def get_semana_da_visita_status():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = 'semana_da_visita_ativa'")
        status = cursor.fetchone()
        cursor.close()
        conn.close()
        return status and status[0] == '1'
    return False

def set_semana_da_visita_status(is_active):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        value = '1' if is_active else '0'
        try:
            cursor.execute("INSERT INTO app_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", ('semana_da_visita_ativa', value))
            conn.commit()
        except Exception as e:
            print(f"Erro ao definir status da semana da visita: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

def viajante_exists_in_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE is_viajante = 1")
        viajante = cursor.fetchone()
        cursor.close()
        conn.close()
        return viajante is not None
    return False

def get_current_active_campanha():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, foto_base64 FROM campanhas WHERE ativa = 1")
        campanha = cursor.fetchone()
        cursor.close()
        conn.close()
        if campanha:
            return {"id": campanha[0], "nome": campanha[1], "foto_base64": campanha[2]}
    return None

def set_campanha_status(campanha_id, is_active):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            if is_active:
                cursor.execute("UPDATE campanhas SET ativa = 0 WHERE id != %s", (campanha_id,))
            cursor.execute("UPDATE campanhas SET ativa = %s WHERE id = %s", (1 if is_active else 0, campanha_id))
            if not is_active:
                cursor.execute("UPDATE campanhas SET data_finalizacao = %s WHERE id = %s", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), campanha_id))
            conn.commit()
        except Exception as e:
            print(f"Erro ao definir status da campanha: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

def get_territorios_cobertos_na_campanha(campanha_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT mapa FROM reservas WHERE campanha_id = %s AND data_baixa IS NOT NULL",
            (campanha_id,)
        )
        cobertos = cursor.fetchall()
        cursor.close()
        conn.close()
        return [c[0] for c in cobertos]
    return []

def get_all_campanhas():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, data_criacao, data_finalizacao, ativa, foto_base64 FROM campanhas ORDER BY data_criacao DESC")
        campanhas = cursor.fetchall()
        cursor.close()
        conn.close()
        return campanhas
    return []

# --- Função Principal do Aplicativo Flet ---
def main(page: ft.Page):
    page.adaptive = True
    page.title = "Hub-Central"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.bgcolor = ft.Colors.BLUE_GREY_900

    current_logged_in_user = ft.Ref[ft.Text]()
    is_admin_logged_in = False
    is_viajante_logged_in = False

    nome_login = ft.TextField(label="Nome de Usuário", width=300, border_radius=10)
    senha_login = ft.TextField(label="Senha", password=True, width=300, border_radius=10)

    # Campos de cadastro de usuário comum, agora para uso do admin
    nome_cadastro_comum = ft.TextField(label="Nome de Usuário", width=300, border_radius=10)
    senha_cadastro_comum = ft.TextField(label="Senha", password=True, width=300, border_radius=10)
    mensagem_cadastro_comum = ft.Text("", visible=False, size=16, weight="bold")

    admin_username_field = ft.TextField(label="Usuário Admin", width=300, border_radius=10)
    admin_password_field = ft.TextField(label="Senha Admin", password=True, width=300, border_radius=10)
    admin_login_message = ft.Text("", visible=False, size=16, weight="bold", color=ft.Colors.RED_500)

    nome_cadastro_viajante = ft.TextField(label="Nome de Usuário (Viajante)", width=300, border_radius=10)
    senha_cadastro_viajante = ft.TextField(label="Senha (Viajante)", password=True, width=300, border_radius=10)
    mensagem_cadastro_viajante = ft.Text("", visible=False, size=16, weight="bold")

    nome_login_viajante = ft.TextField(label="Nome de Usuário (Viajante)", width=300, border_radius=10)
    senha_login_viajante = ft.TextField(label="Senha (Viajante)", password=True, width=300, border_radius=10)
    mensagem_login_viajante = ft.Text("", visible=False, size=16, weight="bold", color=ft.Colors.RED_500)

    nome_nova_campanha_field = ft.TextField(label="Nome da Campanha", width=300, border_radius=10)
    caminho_foto_campanha_field = ft.TextField(
        label="Nome do arquivo da foto (em assets/)",
        hint_text="Ex: campanha_verao.png",
        width=300,
        border_radius=10
    )

    # --- NOVOS ELEMENTOS PARA ALTERAR SENHA DO ADMIN ---
    nova_senha_admin_field = ft.TextField(label="Nova Senha", password=True, width=300, border_radius=10)
    confirmar_nova_senha_admin_field = ft.TextField(label="Confirmar Nova Senha", password=True, width=300, border_radius=10)
    mensagem_alterar_senha_admin = ft.Text("", visible=False, size=16, weight="bold")

    # --- Definições de Funções ---
    def toggle_semana_da_visita(is_active):
        set_semana_da_visita_status(is_active)
        if is_active:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("UPDATE reservas SET data_baixa = %s WHERE data_baixa IS NULL", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
                    conn.commit()
                    page.snack_bar = ft.SnackBar(ft.Text("Todas as reservas ativas foram finalizadas!", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_700)
                    page.snack_bar.open = True
                except Exception as e:
                    print(f"Erro ao finalizar reservas: {e}")
                    conn.rollback()
                finally:
                    cursor.close()
                    conn.close()
        if is_admin_logged_in:
            mostrar_pagina_principal(current_logged_in_user.current)
        else:
            mostrar_tela_login()
        page.update()

    semana_da_visita_checkbox = ft.Checkbox(
        label="Semana da Visita Ativa (Finaliza todas as reservas!)",
        value=get_semana_da_visita_status(),
        on_change=lambda e: toggle_semana_da_visita(e.control.value),
        fill_color=ft.Colors.RED_ACCENT_700,
        label_style=ft.TextStyle(color=ft.Colors.WHITE)
    )

    def login_usuario(e):
        nonlocal is_admin_logged_in, is_viajante_logged_in
        nome = nome_login.value.strip()
        senha = senha_login.value.strip()

        if not nome or not senha:
            page.snack_bar = ft.SnackBar(ft.Text("Preencha todos os campos.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
            page.snack_bar.open = True
            page.update()
            return

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome, senha, is_admin, is_viajante FROM usuarios WHERE nome = %s AND is_admin = 0",
                (nome,)
            )
            usuario_data = cursor.fetchone()
            cursor.close()
            conn.close()

            if usuario_data:
                _, user_name_db, hashed_password_db, _, is_viajante_db = usuario_data
                try:
                    if bcrypt.checkpw(senha.encode('utf-8'), hashed_password_db.encode('utf-8')):
                        is_viajante_logged_in = (is_viajante_db == 1)
                        current_logged_in_user.current = user_name_db
                        mostrar_pagina_principal(user_name_db)
                    else:
                        page.snack_bar = ft.SnackBar(ft.Text("Usuário ou senha inválidos.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                        page.snack_bar.open = True
                        page.update()
                except ValueError:
                    page.snack_bar = ft.SnackBar(ft.Text("Erro de autenticação. Tente novamente.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
                    page.update()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Usuário ou senha inválidos.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                page.snack_bar.open = True
                page.update()

    def cadastrar_usuario_comum_admin_action(e):
        nome = nome_cadastro_comum.value.strip()
        senha = senha_cadastro_comum.value.strip()
        if not nome or not senha:
            mensagem_cadastro_comum.value = "Preencha todos os campos!"
            mensagem_cadastro_comum.color = ft.Colors.RED_500
            mensagem_cadastro_comum.visible = True
            page.update()
            return
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                hashed_senha = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("INSERT INTO usuarios (nome, senha, is_admin, is_viajante) VALUES (%s, %s, 0, 0)", (nome, hashed_senha))
                conn.commit()
                mensagem_cadastro_comum.value = "Usuário comum cadastrado com sucesso!"
                mensagem_cadastro_comum.color = ft.Colors.GREEN_500
                mensagem_cadastro_comum.visible = True
                nome_cadastro_comum.value = ""
                senha_cadastro_comum.value = ""
            except psycopg2.errors.UniqueViolation:
                mensagem_cadastro_comum.value = "Nome de usuário já existe!"
                mensagem_cadastro_comum.color = ft.Colors.RED_500
                mensagem_cadastro_comum.visible = True
                conn.rollback()
            except Exception as ex:
                mensagem_cadastro_comum.value = f"Erro ao cadastrar usuário: {ex}"
                mensagem_cadastro_comum.color = ft.Colors.RED_500
                mensagem_cadastro_comum.visible = True
                conn.rollback()
            finally:
                cursor.close()
                conn.close()
        page.update()

    def cadastrar_administrador_action():
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                hashed_default_admin_password = bcrypt.hashpw(DEFAULT_ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("INSERT INTO usuarios (nome, senha, is_admin) VALUES (%s, %s, 1)", (DEFAULT_ADMIN_USERNAME, hashed_default_admin_password))
                conn.commit()
                admin_login_message.value = "Administrador cadastrado com sucesso! Prossiga com o login."
                admin_login_message.color = ft.Colors.GREEN_500
                admin_login_message.visible = True
                admin_username_field.value = DEFAULT_ADMIN_USERNAME
                admin_password_field.value = ""
                mostrar_tela_admin_login()
            except psycopg2.errors.UniqueViolation:
                admin_login_message.value = "Erro: Administrador já existe ou nome de usuário já está em uso!"
                admin_login_message.color = ft.Colors.RED_500
                admin_login_message.visible = True
                conn.rollback()
            except Exception as e:
                admin_login_message.value = f"Erro ao cadastrar admin: {e}"
                admin_login_message.color = ft.Colors.RED_500
                admin_login_message.visible = True
                conn.rollback()
            finally:
                cursor.close()
                conn.close()
        page.update()

    def login_administrador(e):
        nonlocal is_admin_logged_in, is_viajante_logged_in
        username = admin_username_field.value.strip()
        password = admin_password_field.value.strip()

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome, senha, is_admin FROM usuarios WHERE nome = %s AND is_admin = 1",
                (username,)
            )
            admin_user_data = cursor.fetchone()
            cursor.close()
            conn.close()

            if admin_user_data:
                _, admin_name_db, hashed_password_db, _ = admin_user_data
                try:
                    if bcrypt.checkpw(password.encode('utf-8'), hashed_password_db.encode('utf-8')):
                        is_admin_logged_in = True
                        is_viajante_logged_in = False
                        current_logged_in_user.current = admin_name_db
                        mostrar_pagina_principal(admin_name_db)
                    else:
                        admin_login_message.value = "Credenciais de administrador inválidas!"
                        admin_login_message.visible = True
                        page.update()
                except ValueError:
                    admin_login_message.value = "Erro de autenticação. Tente novamente."
                    admin_login_message.visible = True
                    page.update()
            else:
                admin_login_message.value = "Credenciais de administrador inválidas!"
                admin_login_message.visible = True
                page.update()

    def cadastrar_viajante_action(e):
        if viajante_exists_in_db():
            mensagem_cadastro_viajante.value = "Já existe um S. Viajante cadastrado. Cadastro único permitido."
            mensagem_cadastro_viajante.color = ft.Colors.RED_500
            mensagem_cadastro_viajante.visible = True
            page.update()
            return

        nome = nome_cadastro_viajante.value.strip()
        senha = senha_cadastro_viajante.value.strip()
        if not nome or not senha:
            mensagem_cadastro_viajante.value = "Preencha todos os campos!"
            mensagem_cadastro_viajante.color = ft.Colors.RED_500
            mensagem_cadastro_viajante.visible = True
            page.update()
            return
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                hashed_senha = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("INSERT INTO usuarios (nome, senha, is_admin, is_viajante) VALUES (%s, %s, 0, 1)", (nome, hashed_senha))
                conn.commit()
                mensagem_cadastro_viajante.value = "S. Viajante cadastrado com sucesso! Agora você pode fazer login."
                mensagem_cadastro_viajante.color = ft.Colors.GREEN_500
                mensagem_cadastro_viajante.visible = True
                nome_cadastro_viajante.value = ""
                senha_cadastro_viajante.value = ""
                page.update()
                mostrar_tela_login_viajante()
            except psycopg2.errors.UniqueViolation:
                mensagem_cadastro_viajante.value = "Nome de usuário já existe!"
                mensagem_cadastro_viajante.color = ft.Colors.RED_500
                mensagem_cadastro_viajante.visible = True
                conn.rollback()
            except Exception as ex:
                mensagem_cadastro_viajante.value = f"Erro: {ex}"
                mensagem_cadastro_viajante.color = ft.Colors.RED_500
                mensagem_cadastro_viajante.visible = True
                conn.rollback()
            finally:
                cursor.close()
                conn.close()
        page.update()

    def login_viajante_action(e):
        nonlocal is_admin_logged_in, is_viajante_logged_in
        nome = nome_login_viajante.value.strip()
        senha = senha_login_viajante.value.strip()

        if not nome or not senha:
            mensagem_login_viajante.value = "Preencha todos os campos!"
            mensagem_login_viajante.color = ft.Colors.RED_500
            mensagem_login_viajante.visible = True
            page.update()
            return

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome, senha, is_viajante FROM usuarios WHERE nome = %s AND is_viajante = 1",
                (nome,)
            )
            viajante_user_data = cursor.fetchone()
            cursor.close()
            conn.close()

            if viajante_user_data:
                _, viajante_name_db, hashed_password_db, _ = viajante_user_data
                try:
                    if bcrypt.checkpw(senha.encode('utf-8'), hashed_password_db.encode('utf-8')):
                        is_viajante_logged_in = True
                        is_admin_logged_in = False
                        current_logged_in_user.current = viajante_name_db
                        mostrar_pagina_principal(viajante_name_db)
                    else:
                        mensagem_login_viajante.value = "Nome de usuário ou senha do S. Viajante inválidos!"
                        mensagem_login_viajante.color = ft.Colors.RED_500
                        mensagem_login_viajante.visible = True
                        page.update()
                except ValueError:
                    mensagem_login_viajante.value = "Erro de autenticação. Tente novamente."
                    mensagem_login_viajante.color = ft.Colors.RED_500
                    mensagem_login_viajante.visible = True
                    page.update()
            else:
                mensagem_login_viajante.value = "Nome de usuário ou senha do S. Viajante inválidos!"
                mensagem_login_viajante.color = ft.Colors.RED_500
                mensagem_login_viajante.visible = True
            page.update()

    def criar_campanha_action(e):
        nome_campanha = nome_nova_campanha_field.value.strip()
        nome_arquivo_foto = caminho_foto_campanha_field.value.strip()

        if not nome_campanha or not nome_arquivo_foto:
            page.snack_bar = ft.SnackBar(ft.Text("Por favor, preencha o nome da campanha e o nome do arquivo da foto.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
            page.snack_bar.open = True
            page.update()
            return

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO campanhas (nome, foto_base64, ativa, data_criacao) VALUES (%s, %s, %s, %s)",
                    (nome_campanha, nome_arquivo_foto, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
                page.snack_bar = ft.SnackBar(ft.Text(f"Campanha '{nome_campanha}' criada com sucesso!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                page.snack_bar.open = True
                nome_nova_campanha_field.value = ""
                caminho_foto_campanha_field.value = ""
                mostrar_pagina_gerenciar_campanhas(current_logged_in_user.current)
            except psycopg2.errors.UniqueViolation:
                page.snack_bar = ft.SnackBar(ft.Text("Já existe uma campanha com este nome.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                page.snack_bar.open = True
                conn.rollback()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao criar campanha: {ex}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                page.snack_bar.open = True
                conn.rollback()
            finally:
                cursor.close()
                conn.close()
        page.update()

    def set_campanha_status_handler(is_active, campanha_id):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            if is_active:
                active_campaign = get_current_active_campanha()
                if active_campaign and active_campaign['id'] != campanha_id:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Já existe uma campanha ativa ('{active_campaign['nome']}'). Desative-a primeiro.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
                    page.update()
                    mostrar_pagina_gerenciar_campanhas(current_logged_in_user.current)
                    conn.close()
                    return
                
                cobertos = get_territorios_cobertos_na_campanha(campanha_id)
                if len(cobertos) == len(mapas):
                    page.snack_bar = ft.SnackBar(ft.Text("Esta campanha já está 100% coberta e não pode ser reativada.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
                    page.update()
                    mostrar_pagina_gerenciar_campanhas(current_logged_in_user.current)
                    conn.close()
                    return

            set_campanha_status(campanha_id, is_active)
            page.snack_bar = ft.SnackBar(ft.Text(f"Campanha {'ativada' if is_active else 'desativada'} com sucesso!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500 if is_active else ft.Colors.RED_500)
            page.snack_bar.open = True
            mostrar_pagina_gerenciar_campanhas(current_logged_in_user.current)
            page.update()

    def reservar_mapa(usuario, mapa_info):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            active_campanha = get_current_active_campanha()

            cursor.execute(
                "SELECT mapa FROM reservas WHERE usuario = %s AND data_baixa IS NULL",
                (usuario,)
            )
            mapa_reservado_pelo_usuario = cursor.fetchone()

            if mapa_reservado_pelo_usuario:
                page.snack_bar = ft.SnackBar(ft.Text(f"Você já tem o mapa '{mapa_reservado_pelo_usuario[0]}' reservado. Finalize-o antes de reservar outro.", color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_700)
                page.snack_bar.open = True
            else:
                cursor.execute(
                    "SELECT usuario FROM reservas WHERE mapa = %s AND data_baixa IS NULL",
                    (mapa_info['nome'],)
                )
                mapa_reservado_por_outro = cursor.fetchone()

                if mapa_reservado_por_outro:
                    page.snack_bar = ft.SnackBar(ft.Text(f"O mapa '{mapa_info['nome']}' já está reservado por {mapa_reservado_por_outro[0]}.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
                elif active_campanha:
                    territorios_cobertos = get_territorios_cobertos_na_campanha(active_campanha['id'])
                    if mapa_info['nome'] in territorios_cobertos:
                        page.snack_bar = ft.SnackBar(ft.Text(f"O território '{mapa_info['nome']}' já foi coberto pela campanha '{active_campanha['nome']}'.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                        page.snack_bar.open = True
                    else:
                        try:
                            cursor.execute(
                                "INSERT INTO reservas (mapa, usuario, data_reserva, data_baixa, campanha_id) VALUES (%s, %s, %s, NULL, %s)",
                                (mapa_info['nome'], usuario, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), active_campanha['id'])
                            )
                            conn.commit()
                            page.snack_bar = ft.SnackBar(ft.Text(f"Mapa '{mapa_info['nome']}' reservado com sucesso para a campanha!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                            page.snack_bar.open = True
                        except Exception as e:
                            print(f"Erro ao reservar mapa na campanha: {e}")
                            conn.rollback()
                            page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao reservar mapa: {e}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                            page.snack_bar.open = True
                else:
                    try:
                        cursor.execute(
                            "INSERT INTO reservas (mapa, usuario, data_reserva, data_baixa, campanha_id) VALUES (%s, %s, %s, NULL, NULL)",
                            (mapa_info['nome'], usuario, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        conn.commit()
                        page.snack_bar = ft.SnackBar(ft.Text(f"Mapa '{mapa_info['nome']}' reservado com sucesso!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                        page.snack_bar.open = True
                    except Exception as e:
                        print(f"Erro ao reservar mapa: {e}")
                        conn.rollback()
                        page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao reservar mapa: {e}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                        page.snack_bar.open = True
            cursor.close()
            conn.close()
        mostrar_pagina_escolher_mapa(usuario)
        page.update()

    def baixar_mapa(usuario, mapa_nome):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, campanha_id FROM reservas WHERE mapa = %s AND usuario = %s AND data_baixa IS NULL",
                (mapa_nome, usuario)
            )
            reserva = cursor.fetchone()

            if reserva:
                reserva_id, campanha_id_reserva = reserva
                try:
                    cursor.execute(
                        "UPDATE reservas SET data_baixa = %s WHERE id = %s",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reserva_id)
                    )
                    conn.commit()

                    page.snack_bar = ft.SnackBar(ft.Text(f"Mapa '{mapa_nome}' finalizado com sucesso!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                    page.snack_bar.open = True

                    if campanha_id_reserva:
                        total_territorios = len(mapas)
                        territorios_cobertos_campanha = get_territorios_cobertos_na_campanha(campanha_id_reserva)

                        if len(territorios_cobertos_campanha) == total_territorios:
                            set_campanha_status(campanha_id_reserva, False)
                            page.snack_bar = ft.SnackBar(ft.Text(f"Todos os territórios da campanha foram cobertos! Campanha finalizada.", color=ft.Colors.WHITE), bgcolor=ft.Colors.AMBER_700)
                            page.snack_bar.open = True
                except Exception as e:
                    print(f"Erro ao baixar mapa: {e}")
                    conn.rollback()
                    page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao finalizar mapa: {e}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro: Não foi possível encontrar a reserva ativa para '{mapa_nome}'.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                page.snack_bar.open = True

            cursor.close()
            conn.close()
        mostrar_pagina_escolher_mapa(usuario)
        page.update()

    def baixar_mapa_meus_mapas(usuario, mapa_nome):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, campanha_id FROM reservas WHERE mapa = %s AND usuario = %s AND data_baixa IS NULL",
                (mapa_nome, usuario)
            )
            reserva = cursor.fetchone()

            if reserva:
                reserva_id, campanha_id_reserva = reserva
                try:
                    cursor.execute(
                        "UPDATE reservas SET data_baixa = %s WHERE id = %s",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reserva_id)
                    )
                    conn.commit()

                    page.snack_bar = ft.SnackBar(ft.Text(f"Mapa '{mapa_nome}' finalizado com sucesso!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                    page.snack_bar.open = True

                    if campanha_id_reserva:
                        total_territorios = len(mapas)
                        territorios_cobertos_campanha = get_territorios_cobertos_na_campanha(campanha_id_reserva)

                        if len(territorios_cobertos_campanha) == total_territorios:
                            set_campanha_status(campanha_id_reserva, False)
                            page.snack_bar = ft.SnackBar(ft.Text(f"Todos os territórios da campanha foram cobertos! Campanha finalizada.", color=ft.Colors.WHITE), bgcolor=ft.Colors.AMBER_700)
                            page.snack_bar.open = True
                except Exception as e:
                    print(f"Erro ao baixar mapa: {e}")
                    conn.rollback()
                    page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao finalizar mapa: {e}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro: Não foi possível encontrar a reserva ativa para '{mapa_nome}'.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                page.snack_bar.open = True

            cursor.close()
            conn.close()
        mostrar_meus_mapas(usuario)
        page.update()
    
    def open_fullscreen_image_campanha(e, img_src_path):
        # Para imagens da campanha, onde o zoom não é a prioridade, mantemos o simples
        page.dialog = ft.AlertDialog(
            modal=True,
            content=ft.Image(src=img_src_path, fit=ft.ImageFit.CONTAIN),
            actions=[
                ft.TextButton("Fechar", on_click=lambda e: page.client_storage.set("dialog_open", "false") or close_dialog(e))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=lambda e: page.client_storage.set("dialog_open", "false")
        )
        page.client_storage.set("dialog_open", "true")
        page.open(page.dialog)
        page.update()

    def open_dialog(dialog_content):
        page.dialog = ft.AlertDialog(
            modal=True,
            content=dialog_content,
            actions=[
                ft.TextButton("Fechar", on_click=close_dialog)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=close_dialog
        )
        page.open(page.dialog)
        page.update()

    def close_dialog(e):
        page.dialog.open = False
        page.update()

    # --- Funções de Exibição de Páginas ---
    def mostrar_tela_login(e=None):
        nonlocal is_admin_logged_in, is_viajante_logged_in
        is_admin_logged_in = False
        is_viajante_logged_in = False
        page.controls.clear()

        is_semana_ativa = get_semana_da_visita_status()

        login_elements = []
        if not is_semana_ativa:
            login_elements.extend([
                ft.Text("Login de Usuário", size=20, weight="bold", color=ft.Colors.WHITE),
                nome_login,
                senha_login,
                ft.ElevatedButton(
                    "Entrar",
                    on_click=login_usuario,
                    width=300,
                    height=40,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE_800,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10)
                    )
                ),
                ft.Divider(),
            ])
        else:
            login_elements.append(
                ft.Text("Semana da Visita Ativa", size=20, weight="bold", color=ft.Colors.YELLOW_600)
            )

        if is_semana_ativa:
            if not viajante_exists_in_db():
                login_elements.append(
                    ft.ElevatedButton(
                        "Cadastrar S. Viajante",
                        on_click=mostrar_tela_cadastro_viajante,
                        width=300,
                        height=40,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PURPLE_600,
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=10)
                        )
                    )
                )
            else:
                login_elements.append(
                    ft.ElevatedButton(
                        "Login do S. Viajante",
                        on_click=mostrar_tela_login_viajante,
                        width=300,
                        height=40,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PURPLE_600,
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=10)
                        )
                    )
                )
            login_elements.append(ft.Divider())

        login_elements.append(
            ft.ElevatedButton(
                "Acesso de Administrador",
                on_click=mostrar_tela_admin_login,
                width=300,
                height=40,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.DEEP_ORANGE_600,
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=10)
                )
            )
        )

        page.add(
            ft.Column(
                [
                    ft.Text("Bem-vindo ao Hub-Central!", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Text("Mapas da Central", size=24, weight="bold", color=ft.Colors.BLUE_GREY_200),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLUE_GREY_800),
                            content=ft.Column(
                                login_elements,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        page.update()

    def mostrar_tela_cadastro_comum_admin(e=None):
        nome_cadastro_comum.value = ""
        senha_cadastro_comum.value = ""
        mensagem_cadastro_comum.visible = False
        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Cadastrar Novo Usuário Comum", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLUE_GREY_800),
                            content=ft.Column(
                                [
                                    nome_cadastro_comum,
                                    senha_cadastro_comum,
                                    ft.ElevatedButton(
                                        "Cadastrar Usuário",
                                        on_click=cadastrar_usuario_comum_admin_action,
                                        width=300,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            bgcolor=ft.Colors.GREEN_700,
                                            color=ft.Colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    ),
                                    ft.TextButton("Voltar para Painel Admin", on_click=lambda e: mostrar_pagina_principal(current_logged_in_user.current), style=ft.ButtonStyle(color=ft.Colors.BLUE_200)),
                                    mensagem_cadastro_comum
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        page.update()

    def mostrar_tela_cadastro_viajante(e=None):
        nome_cadastro_viajante.value = ""
        senha_cadastro_viajante.value = ""
        mensagem_cadastro_viajante.visible = False
        page.controls.clear()

        btn_cadastrar_viajante_element = ft.ElevatedButton(
            "Cadastrar S. Viajante",
            on_click=cadastrar_viajante_action,
            width=300,
            height=40,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PURPLE_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=10)
            ),
            disabled=viajante_exists_in_db()
        )

        page.add(
            ft.Column(
                [
                    ft.Text("Cadastro do S. Viajante", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.PURPLE_800),
                            content=ft.Column(
                                [
                                    ft.Text("Cadastro Único para o S. Viajante", size=16, color=ft.Colors.WHITE70),
                                    nome_cadastro_viajante,
                                    senha_cadastro_viajante,
                                    btn_cadastrar_viajante_element,
                                    ft.TextButton("Voltar para Login", on_click=mostrar_tela_login, style=ft.ButtonStyle(color=ft.Colors.PURPLE_200)),
                                    mensagem_cadastro_viajante
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        page.update()

    def mostrar_tela_login_viajante(e=None):
        nome_login_viajante.value = ""
        senha_login_viajante.value = ""
        mensagem_login_viajante.visible = False
        page.controls.clear()

        if not viajante_exists_in_db():
            page.snack_bar = ft.SnackBar(ft.Text("Nenhum S. Viajante cadastrado. Cadastre-se primeiro.", color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_700)
            page.snack_bar.open = True
            mostrar_tela_cadastro_viajante()
            return

        page.add(
            ft.Column(
                [
                    ft.Text("Login do S. Viajante", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.PURPLE_800),
                            content=ft.Column(
                                [
                                    nome_login_viajante,
                                    senha_login_viajante,
                                    ft.ElevatedButton(
                                        "Entrar como S. Viajante",
                                        on_click=login_viajante_action,
                                        width=300,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            bgcolor=ft.Colors.PURPLE_700,
                                            color=ft.Colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    ),
                                    ft.TextButton("Voltar para Login Principal", on_click=mostrar_tela_login, style=ft.ButtonStyle(color=ft.Colors.PURPLE_200)),
                                    mensagem_login_viajante
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        page.update()

    def mostrar_tela_admin_login(e=None):
        admin_username_field.value = ""
        admin_password_field.value = ""
        admin_login_message.visible = False

        btn_cadastrar_admin_local = ft.ElevatedButton(
            "Cadastrar Admin",
            on_click=lambda e: cadastrar_administrador_action(),
            width=300,
            height=40,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_700,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=10)
            ),
            visible=not admin_exists_in_db()
        )

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Login de Administrador", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.DEEP_ORANGE_900),
                            content=ft.Column(
                                [
                                    admin_username_field,
                                    admin_password_field,
                                    ft.ElevatedButton(
                                        "Entrar como Admin",
                                        on_click=login_administrador,
                                        width=300,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            bgcolor=ft.Colors.DEEP_ORANGE_600,
                                            color=ft.Colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    ),
                                    btn_cadastrar_admin_local,
                                    ft.TextButton("Voltar", on_click=mostrar_tela_login, style=ft.ButtonStyle(color=ft.Colors.ORANGE_200)),
                                    admin_login_message
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        page.update()

    def mostrar_pagina_principal(nome_usuario):
        page.controls.clear()

        common_buttons = [
            ft.ElevatedButton("Escolher mapa", on_click=lambda e: mostrar_pagina_escolher_mapa(nome_usuario)),
            ft.ElevatedButton("Meus mapas", on_click=lambda e: mostrar_meus_mapas(nome_usuario)),
            ft.ElevatedButton("Mapas Mais Trabalhados", on_click=lambda e: mostrar_grafico_mais_trabalhados(nome_usuario)),
        ]

        admin_buttons = []
        if is_admin_logged_in:
            admin_buttons.append(semana_da_visita_checkbox)
            admin_buttons.append(ft.ElevatedButton("Cadastrar Usuário Comum", on_click=mostrar_tela_cadastro_comum_admin, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_ACCENT_700, color=ft.Colors.WHITE)))
            admin_buttons.append(ft.ElevatedButton("Gerenciar Campanhas", on_click=lambda e: mostrar_pagina_gerenciar_campanhas(nome_usuario), style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_600, color=ft.Colors.WHITE)))
            admin_buttons.append(ft.ElevatedButton("Histórico de Reservas", on_click=lambda e: mostrar_pagina_historico_visita(nome_usuario)))
            admin_buttons.append(ft.ElevatedButton("Gerenciar Reservas", on_click=lambda e: mostrar_pagina_gerenciar_reservas_admin(nome_usuario)))
            # NOVO: Botão para alterar senha do admin
            admin_buttons.append(ft.ElevatedButton("Alterar Senha do Admin", on_click=lambda e: mostrar_pagina_alterar_senha_admin(nome_usuario), style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_PURPLE_600, color=ft.Colors.WHITE)))


        page.add(
            ft.Column(
                [
                    ft.Text(f"Bem-vindo, {nome_usuario}!", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.ResponsiveRow(
                        [ft.Column(col=12, controls=[btn]) for btn in common_buttons + admin_buttons],
                        spacing=10, run_spacing=10
                    ),
                    ft.ElevatedButton("Sair", on_click=mostrar_tela_login, style=ft.ButtonStyle(
                        bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10)
                    ))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=30
            )
        )
        page.update()

    def mostrar_pagina_escolher_mapa(nome_usuario_logado):
        conn = get_db_connection()
        reservas = []
        mapa_reservado_pelo_usuario_logado = None
        active_campanha = get_current_active_campanha()
        territorios_cobertos_campanha = []

        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT mapa, usuario, campanha_id FROM reservas WHERE data_baixa IS NULL"
            )
            reservas = cursor.fetchall()

            cursor.execute(
                "SELECT mapa FROM reservas WHERE usuario = %s AND data_baixa IS NULL",
                (nome_usuario_logado,)
            )
            mapa_reservado_pelo_usuario_logado = cursor.fetchone()
            cursor.close()
            conn.close()

        if active_campanha:
            territorios_cobertos_campanha = get_territorios_cobertos_na_campanha(active_campanha['id'])

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Escolher Território", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Container(
                        expand=True,
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_800),
                        content=ft.ListView(expand=True, spacing=10, padding=10)
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_usuario_logado),
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )

        lista_mapas = page.controls[0].controls[1].content

        for i, mapa_info in enumerate(mapas):
            reservado_por_outro_data = next(((r[1], r[2]) for r in reservas if r[0] == mapa_info['nome'] and r[1] != nome_usuario_logado), None)
            is_reserved_by_current_user = (mapa_reservado_pelo_usuario_logado and mapa_reservado_pelo_usuario_logado[0] == mapa_info['nome'])

            is_coberto_campanha = False
            if active_campanha:
                is_coberto_campanha = (mapa_info['nome'] in territorios_cobertos_campanha)

            status_texto = ""
            status_cor = ""
            mapa_actions = []

            if is_reserved_by_current_user:
                status_texto = f"Reservado para você ({nome_usuario_logado})"
                status_cor = ft.Colors.BLUE_400
                mapa_actions.append(ft.ElevatedButton(
                    "Finalizar Território",
                    on_click=lambda e, mapa_name=mapa_info['nome']: baixar_mapa(nome_usuario_logado, mapa_name),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
                ))
            elif reservado_por_outro_data:
                status_texto = f"Reservado para {reservado_por_outro_data[0]}"
                status_cor = ft.Colors.RED_400
            elif is_coberto_campanha:
                status_texto = f"Coberto pela campanha: {active_campanha['nome']}"
                status_cor = ft.Colors.GREEN_400
            else:
                status_texto = "Livre"
                status_cor = ft.Colors.GREEN_400
                mapa_actions.append(ft.ElevatedButton(
                    "Reservar",
                    on_click=lambda e, mapa=mapa_info: reservar_mapa(nome_usuario_logado, mapa),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE)
                ))

            if not is_coberto_campanha:
                mapa_actions.append(ft.ElevatedButton(
                    "Ver Mapa",
                    on_click=lambda e, index=i: ver_mapa_correspondente(e, index),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ft.Colors.GREY_700, color=ft.Colors.WHITE)
                ))

            campanha_info_display = []
            if active_campanha:
                campanha_foto_src = f"/{active_campanha['foto_base64']}" if active_campanha['foto_base64'] else ""
                
                if campanha_foto_src:
                    campanha_info_display.append(ft.Container(
                        content=ft.Row([
                            ft.GestureDetector(
                                content=ft.Image(
                                    src=campanha_foto_src,
                                    width=50, height=50,
                                    fit=ft.ImageFit.COVER,
                                    border_radius=ft.border_radius.all(5),
                                    tooltip="Clique para ampliar"
                                ),
                                on_tap=lambda e, img_path=campanha_foto_src: open_fullscreen_image_campanha(e, img_path)
                            ),
                            ft.Text(f"Campanha: {active_campanha['nome']}", color=ft.Colors.AMBER_200, size=14, weight="bold")
                        ], alignment=ft.MainAxisAlignment.START, spacing=10),
                        padding=ft.padding.only(bottom=5)
                    ))

            card = ft.Card(
                elevation=5,
                content=ft.Container(
                    padding=15,
                    border_radius=10,
                    bgcolor=ft.Colors.BLUE_GREY_800 if not (reservado_por_outro_data or is_reserved_by_current_user or is_coberto_campanha) else ft.Colors.BLUE_GREY_900,
                    content=ft.Column(
                        controls=[
                            ft.Text(f"{mapa_info['nome']} : {mapa_info['descricao']}", size=18, weight="bold", color=ft.Colors.WHITE),
                            *campanha_info_display,
                            ft.Text(status_texto, color=status_cor, size=14),
                            ft.Row(alignment=ft.MainAxisAlignment.END, controls=mapa_actions)
                        ]
                    )
                )
            )
            lista_mapas.controls.append(card)
        page.update()

    def ver_mapa_correspondente(e, index_mapa):
        image_path = f"/mapa{index_mapa + 1}.png"

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text(f"Visualizando Território {index_mapa + 1}", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Container(
                        expand=True, # Garante que o container ocupe todo o espaço disponível
                        alignment=ft.alignment.center,
                        content=ft.InteractiveViewer(
                            content=ft.Image(src=image_path, fit=ft.ImageFit.CONTAIN, scale=1.0),
                            min_scale=0.5,
                            max_scale=4.0,
                            boundary_margin=ft.padding.all(0),
                            constrained=True,
                            pan_enabled=True,
                            scale_enabled=True,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        ),
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_escolher_mapa(current_logged_in_user.current),
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )
        page.update()

    def mostrar_meus_mapas(nome_usuario):
        conn = get_db_connection()
        minhas_reservas = []
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT mapa, data_reserva, campanha_id FROM reservas WHERE usuario = %s AND data_baixa IS NULL",
                (nome_usuario,)
            )
            minhas_reservas = cursor.fetchall()
            cursor.close()
            conn.close()

        page.controls.clear()

        minhas_reservas_list_controls = []
        if not minhas_reservas:
            minhas_reservas_list_controls.append(ft.Text("Você não possui mapas reservados.", color=ft.Colors.WHITE70, size=16))
        else:
            for mapa_nome, data_reserva, campanha_id_reserva in minhas_reservas:
                campanha_nome = ""
                if campanha_id_reserva:
                    conn_inner = get_db_connection()
                    if conn_inner:
                        cursor_inner = conn_inner.cursor()
                        cursor_inner.execute("SELECT nome FROM campanhas WHERE id = %s", (campanha_id_reserva,))
                        campanha_data = cursor_inner.fetchone()
                        cursor_inner.close()
                        conn_inner.close()
                        if campanha_data:
                            campanha_nome = f" (Campanha: {campanha_data[0]})"

                minhas_reservas_list_controls.append(
                    ft.Card(
                        elevation=5,
                        content=ft.Container(
                            padding=15,
                            border_radius=10,
                            bgcolor=ft.Colors.BLUE_GREY_800,
                            content=ft.Column(
                                [
                                    ft.Text(f"Território: {mapa_nome}{campanha_nome}", size=18, weight="bold", color=ft.Colors.WHITE),
                                    ft.Text(f"Reservado em: {data_reserva}", size=14, color=ft.Colors.WHITE70),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.END,
                                        controls=[
                                            ft.ElevatedButton(
                                                "Finalizar Território",
                                                on_click=lambda e, m=mapa_nome: baixar_mapa_meus_mapas(nome_usuario, m),
                                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    )
                )

        page.add(
            ft.Column(
                [
                    ft.Text(f"Meus Territórios", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Container(
                        expand=True,
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_800),
                        content=ft.ListView(expand=True, spacing=10, padding=10, controls=minhas_reservas_list_controls)
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )
        page.update()

    def mostrar_grafico_mais_trabalhados(nome_usuario):
        conn = get_db_connection()
        contagem_mapas = []
        if conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT mapa, COUNT(*) FROM reservas WHERE data_baixa IS NOT NULL GROUP BY mapa ORDER BY COUNT(*) DESC LIMIT 5"
            )
            contagem_mapas = cursor.fetchall()
            cursor.close()
            conn.close()

        mapas_nomes = [item[0] for item in contagem_mapas]
        mapas_quantidades = [item[1] for item in contagem_mapas]

        plt.figure(figsize=(10, 6))
        plt.bar(mapas_nomes, mapas_quantidades, color='skyblue')
        plt.xlabel("Território")
        plt.ylabel("Número de Vezes Trabalhado")
        plt.title("Top 5 Territórios Mais Trabalhados")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Territórios Mais Trabalhados", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Container(
                        content=ft.Image(src_base64=img_base64, fit=ft.ImageFit.CONTAIN),
                        alignment=ft.alignment.center,
                        expand=True,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=10,
                        padding=10
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )
        page.update()

    def mostrar_pagina_historico_visita(nome_usuario):
        conn = get_db_connection()
        historico_reservas = []
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT r.mapa, r.usuario, r.data_reserva, r.data_baixa, c.nome FROM reservas r LEFT JOIN campanhas c ON r.campanha_id = c.id ORDER BY r.data_reserva DESC"
            )
            historico_reservas = cursor.fetchall()
            cursor.close()
            conn.close()

        page.controls.clear()

        historico_list_controls = []
        if not historico_reservas:
            historico_list_controls.append(ft.Text("Nenhum histórico de reservas encontrado.", color=ft.Colors.WHITE70, size=16))
        else:
            for mapa, usuario_reserva, data_reserva, data_baixa, campanha_nome_historico in historico_reservas:
                status_baixa = f"Baixado em: {data_baixa}" if data_baixa else "Ativo"
                status_color = ft.Colors.GREEN_400 if data_baixa else ft.Colors.RED_400
                campanha_info = f" (Campanha: {campanha_nome_historico})" if campanha_nome_historico else ""

                historico_list_controls.append(
                    ft.Card(
                        elevation=5,
                        content=ft.Container(
                            padding=15,
                            border_radius=10,
                            bgcolor=ft.Colors.BLUE_GREY_800,
                            content=ft.Column(
                                [
                                    ft.Text(f"Território: {mapa}{campanha_info}", size=18, weight="bold", color=ft.Colors.WHITE),
                                    ft.Text(f"Usuário: {usuario_reserva}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(f"Reservado em: {data_reserva}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(status_baixa, size=14, color=status_color)
                                ]
                            )
                        )
                    )
                )

        page.add(
            ft.Column(
                [
                    ft.Text("Histórico de Reservas", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Container(
                        expand=True,
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_800),
                        content=ft.ListView(expand=True, spacing=10, padding=10, controls=historico_list_controls)
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )
        page.update()

    def mostrar_pagina_gerenciar_reservas_admin(nome_usuario):
        conn = get_db_connection()
        reservas_ativas = []
        usuarios = []
        todos_mapas = [m['nome'] for m in mapas]

        if conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, mapa, usuario, data_reserva, campanha_id FROM reservas WHERE data_baixa IS NULL ORDER BY data_reserva DESC"
            )
            reservas_ativas = cursor.fetchall()

            cursor.execute("SELECT nome FROM usuarios")
            usuarios = [u[0] for u in cursor.fetchall()]
            cursor.close()
            conn.close()

        dropdown_usuarios = ft.Dropdown(
            options=[ft.dropdown.Option(u) for u in usuarios],
            label="Selecione o usuário",
            width=300
        )

        dropdown_mapas = ft.Dropdown(
            options=[ft.dropdown.Option(m) for m in todos_mapas],
            label="Selecione o território",
            width=300
        )

        def reservar_como_admin(e):
            usuario_selecionado = dropdown_usuarios.value
            mapa_selecionado = dropdown_mapas.value

            if not usuario_selecionado or not mapa_selecionado:
                page.snack_bar = ft.SnackBar(ft.Text("Selecione um usuário e um território.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                page.snack_bar.open = True
                page.update()
                return

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT usuario FROM reservas WHERE mapa = %s AND data_baixa IS NULL",
                    (mapa_selecionado,)
                )
                mapa_reservado = cursor.fetchone()

                if mapa_reservado:
                    page.snack_bar = ft.SnackBar(ft.Text(f"O território '{mapa_selecionado}' já está reservado por {mapa_reservado[0]}.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                    page.snack_bar.open = True
                else:
                    cursor.execute(
                        "SELECT mapa FROM reservas WHERE usuario = %s AND data_baixa IS NULL",
                        (usuario_selecionado,)
                    )
                    usuario_tem_reserva = cursor.fetchone()

                    if usuario_tem_reserva:
                        page.snack_bar = ft.SnackBar(ft.Text(f"O usuário '{usuario_selecionado}' já tem o território '{usuario_tem_reserva[0]}' reservado.", color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_700)
                        page.snack_bar.open = True
                    else:
                        try:
                            cursor.execute(
                                "INSERT INTO reservas (mapa, usuario, data_reserva, data_baixa, campanha_id) VALUES (%s, %s, %s, NULL, NULL)",
                                (mapa_selecionado, usuario_selecionado, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            )
                            conn.commit()
                            page.snack_bar = ft.SnackBar(ft.Text(f"Território '{mapa_selecionado}' reservado para '{usuario_selecionado}' com sucesso!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                            page.snack_bar.open = True
                            mostrar_pagina_gerenciar_reservas_admin(nome_usuario)
                        except Exception as e:
                            print(f"Erro ao reservar como admin: {e}")
                            conn.rollback()
                            page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao reservar: {e}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                            page.snack_bar.open = True
                cursor.close()
                conn.close()
            page.update()

        lista_reservas_ativas_controls = []

        if not reservas_ativas:
            lista_reservas_ativas_controls.append(ft.Text("Nenhuma reserva ativa no momento.", color=ft.Colors.WHITE70, size=16))
        else:
            for reserva_id, mapa, usuario_reserva, data_reserva, campanha_id_reserva_admin in reservas_ativas:
                campanha_info_admin = ""
                if campanha_id_reserva_admin:
                    conn_inner = get_db_connection()
                    if conn_inner:
                        cursor_inner = conn_inner.cursor()
                        cursor_inner.execute("SELECT nome FROM campanhas WHERE id = %s", (campanha_id_reserva_admin,))
                        campanha_data_admin = cursor_inner.fetchone()
                        cursor_inner.close()
                        conn_inner.close()
                        if campanha_data_admin:
                            campanha_info_admin = f" (Campanha: {campanha_data_admin[0]})"

                def finalizar_reserva_admin(e, r_id=reserva_id, m=mapa, u=usuario_reserva, camp_id=campanha_id_reserva_admin):
                    conn_inner = get_db_connection()
                    if conn_inner:
                        cursor_inner = conn_inner.cursor()
                        try:
                            cursor_inner.execute(
                                "UPDATE reservas SET data_baixa = %s WHERE id = %s",
                                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r_id)
                            )
                            conn_inner.commit()
                            cursor_inner.close()
                            conn_inner.close()

                            page.snack_bar = ft.SnackBar(ft.Text(f"Reserva do mapa '{m}' por '{u}' finalizada!", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_500)
                            page.snack_bar.open = True

                            if camp_id:
                                total_territorios = len(mapas)
                                territorios_cobertos_campanha = get_territorios_cobertos_na_campanha(camp_id)
                                if len(territorios_cobertos_campanha) == total_territorios:
                                    set_campanha_status(camp_id, False)
                                    page.snack_bar = ft.SnackBar(ft.Text(f"Todos os territórios da campanha foram cobertos! Campanha finalizada.", color=ft.Colors.WHITE), bgcolor=ft.Colors.AMBER_700)
                                    page.snack_bar.open = True
                        except Exception as e:
                            print(f"Erro ao finalizar reserva como admin: {e}")
                            conn_inner.rollback()
                            page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao finalizar reserva: {e}", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_500)
                            page.snack_bar.open = True
                            cursor_inner.close()
                            conn_inner.close()

                    mostrar_pagina_gerenciar_reservas_admin(nome_usuario)
                    page.update()

                lista_reservas_ativas_controls.append(
                    ft.Card(
                        elevation=5,
                        content=ft.Container(
                            padding=15,
                            border_radius=10,
                            bgcolor=ft.Colors.BLUE_GREY_800,
                            content=ft.Column(
                                [
                                    ft.Text(f"Território: {mapa}{campanha_info_admin}", size=18, weight="bold", color=ft.Colors.WHITE),
                                    ft.Text(f"Usuário: {usuario_reserva}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(f"Reservado em: {data_reserva}", size=14, color=ft.Colors.WHITE70),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.END,
                                        controls=[
                                            ft.ElevatedButton(
                                                "Finalizar (Admin)",
                                                on_click=lambda e, r_id=reserva_id, m=mapa, u=usuario_reserva, camp_id=campanha_id_reserva_admin: finalizar_reserva_admin(e, r_id, m, u, camp_id),
                                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE)
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    )
                )

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Gerenciar Reservas (Admin)", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),

                    ft.Card(
                        elevation=5,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.DEEP_ORANGE_800),
                            content=ft.Column(
                                [
                                    ft.Text("Reservar Território para Usuário", size=18, weight="bold", color=ft.Colors.WHITE),
                                    dropdown_usuarios,
                                    dropdown_mapas,
                                    ft.ElevatedButton(
                                        "Reservar como Admin",
                                        on_click=reservar_como_admin,
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE)
                                    )
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    ),

                    ft.Text("Reservas Ativas", size=24, weight="bold", color=ft.Colors.BLUE_GREY_200),
                    ft.Container(
                        expand=True,
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_800),
                        content=ft.ListView(expand=True, spacing=10, padding=10, controls=lista_reservas_ativas_controls)
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                spacing=20
            )
        )
        page.update()

    def mostrar_pagina_gerenciar_campanhas(nome_usuario):
        campanhas = get_all_campanhas()

        lista_campanhas_controls = []
        if not campanhas:
            lista_campanhas_controls.append(ft.Text("Nenhuma campanha criada ainda.", color=ft.Colors.WHITE70, size=16))
        else:
            for c_id, c_nome, c_data_criacao, c_data_finalizacao, c_ativa, c_foto_filename in campanhas:
                status_texto = "Ativa" if c_ativa else "Inativa"
                status_color = ft.Colors.GREEN_500 if c_ativa else ft.Colors.RED_500
                
                campanha_img_src = f"/{c_foto_filename}" if c_foto_filename else ""

                lista_campanhas_controls.append(
                    ft.Card(
                        elevation=5,
                        content=ft.Container(
                            padding=15,
                            border_radius=10,
                            bgcolor=ft.Colors.BLUE_GREY_800,
                            content=ft.Column(
                                [
                                    ft.Text(f"Nome: {c_nome}", size=18, weight="bold", color=ft.Colors.WHITE),
                                    ft.Text(f"Criada em: {c_data_criacao}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(f"Finalizada em: {c_data_finalizacao if c_data_finalizacao else 'N/A'}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(f"Status: {status_texto}", size=14, color=status_color),
                                    
                                    ft.Container(
                                        content=ft.Image(src=campanha_img_src, width=100, height=100, fit=ft.ImageFit.COVER, border_radius=ft.border_radius.all(5)),
                                        visible=bool(campanha_img_src)
                                    ),
                                    
                                    ft.Row(
                                        controls=[
                                            ft.Checkbox(
                                                label="Ativar Campanha",
                                                value=bool(c_ativa),
                                                on_change=lambda e, id=c_id: set_campanha_status_handler(e.control.value, id),
                                                fill_color=ft.Colors.AMBER_700,
                                                label_style=ft.TextStyle(color=ft.Colors.WHITE)
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    )
                )

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Gerenciar Campanhas", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLUE_GREY_800),
                            content=ft.Column(
                                [
                                    ft.Text("Criar Nova Campanha", size=18, weight="bold", color=ft.Colors.WHITE),
                                    nome_nova_campanha_field,
                                    caminho_foto_campanha_field,
                                    ft.ElevatedButton(
                                        "Criar Campanha",
                                        on_click=criar_campanha_action,
                                        width=300,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            bgcolor=ft.Colors.AMBER_700,
                                            color=ft.Colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    ),
                                ]
                            )
                        )
                    ),
                    ft.Text("Campanhas Existentes", size=24, weight="bold", color=ft.Colors.BLUE_GREY_200),
                    ft.Container(
                        expand=True,
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_800),
                        content=ft.ListView(expand=True, spacing=10, padding=10, controls=lista_campanhas_controls)
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE)),
                    ft.ElevatedButton("Ver Histórico de Campanhas", on_click=lambda e: mostrar_historico_campanhas(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                spacing=20
            )
        )
        page.update()

    def mostrar_historico_campanhas(nome_usuario):
        campanhas = get_all_campanhas()

        historico_list_controls = []
        if not campanhas:
            historico_list_controls.append(ft.Text("Nenhum histórico de campanhas encontrado.", color=ft.Colors.WHITE70, size=16))
        else:
            for c_id, c_nome, c_data_criacao, c_data_finalizacao, c_ativa, c_foto_filename in campanhas:
                status_texto = "Ativa" if c_ativa else "Inativa"
                status_color = ft.Colors.GREEN_400 if c_ativa else ft.Colors.RED_400
                
                campanha_img_src = f"/{c_foto_filename}" if c_foto_filename else ""

                historico_list_controls.append(
                    ft.Card(
                        elevation=5,
                        content=ft.Container(
                            padding=15,
                            border_radius=10,
                            bgcolor=ft.Colors.BLUE_GREY_800,
                            content=ft.Column(
                                [
                                    ft.Text(f"Nome: {c_nome}", size=18, weight="bold", color=ft.Colors.WHITE),
                                    ft.Text(f"Criada em: {c_data_criacao}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(f"Finalizada em: {c_data_finalizacao if c_data_finalizacao else 'N/A'}", size=14, color=ft.Colors.WHITE70),
                                    ft.Text(f"Status: {status_texto}", size=14, color=status_color),
                                    ft.Container(
                                        content=ft.Image(src=campanha_img_src, width=80, height=80, fit=ft.ImageFit.COVER, border_radius=ft.border_radius.all(5)),
                                        visible=bool(campanha_img_src)
                                    ),
                                ]
                            )
                        )
                    )
                )

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Histórico de Campanhas", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Container(
                        expand=True,
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_800),
                        content=ft.ListView(expand=True, spacing=10, padding=10, controls=historico_list_controls)
                    ),
                    ft.ElevatedButton("Voltar", on_click=lambda e: mostrar_pagina_gerenciar_campanhas(nome_usuario),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_700, color=ft.Colors.WHITE))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )
        page.update()

    # --- NOVA PÁGINA PARA ALTERAR SENHA DO ADMIN ---
    def mostrar_pagina_alterar_senha_admin(nome_admin):
        nova_senha_admin_field.value = ""
        confirmar_nova_senha_admin_field.value = ""
        mensagem_alterar_senha_admin.visible = False

        def alterar_senha_admin_action(e):
            nova_senha = nova_senha_admin_field.value.strip()
            confirmar_nova_senha = confirmar_nova_senha_admin_field.value.strip()

            if not nova_senha or not confirmar_nova_senha:
                mensagem_alterar_senha_admin.value = "Preencha todos os campos!"
                mensagem_alterar_senha_admin.color = ft.Colors.RED_500
                mensagem_alterar_senha_admin.visible = True
                page.update()
                return

            if nova_senha != confirmar_nova_senha:
                mensagem_alterar_senha_admin.value = "As senhas não coincidem!"
                mensagem_alterar_senha_admin.color = ft.Colors.RED_500
                mensagem_alterar_senha_admin.visible = True
                page.update()
                return
            
            if len(nova_senha) < 6: # Exemplo: exigir senha de pelo menos 6 caracteres
                mensagem_alterar_senha_admin.value = "A senha deve ter pelo menos 6 caracteres."
                mensagem_alterar_senha_admin.color = ft.Colors.RED_500
                mensagem_alterar_senha_admin.visible = True
                page.update()
                return

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    hashed_nova_senha = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                    cursor.execute(
                        "UPDATE usuarios SET senha = %s WHERE nome = %s AND is_admin = 1",
                        (hashed_nova_senha, nome_admin)
                    )
                    conn.commit()
                    conn.close()

                    mensagem_alterar_senha_admin.value = "Senha alterada com sucesso!"
                    mensagem_alterar_senha_admin.color = ft.Colors.GREEN_500
                    mensagem_alterar_senha_admin.visible = True
                    nova_senha_admin_field.value = ""
                    confirmar_nova_senha_admin_field.value = ""
                    page.update()

                except Exception as ex:
                    mensagem_alterar_senha_admin.value = f"Erro ao alterar senha: {ex}"
                    mensagem_alterar_senha_admin.color = ft.Colors.RED_500
                    mensagem_alterar_senha_admin.visible = True
                    conn.rollback()
                    conn.close()
                page.update()

        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text(f"Alterar Senha do Admin ({nome_admin})", size=30, weight="bold", color=ft.Colors.BLUE_GREY_100),
                    ft.Card(
                        width=400,
                        elevation=15,
                        content=ft.Container(
                            padding=20,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.DEEP_PURPLE_800),
                            content=ft.Column(
                                [
                                    nova_senha_admin_field,
                                    confirmar_nova_senha_admin_field,
                                    ft.ElevatedButton(
                                        "Alterar Senha",
                                        on_click=alterar_senha_admin_action,
                                        width=300,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            bgcolor=ft.Colors.DEEP_PURPLE_600,
                                            color=ft.Colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=10)
                                        )
                                    ),
                                    ft.TextButton("Voltar", on_click=lambda e: mostrar_pagina_principal(nome_admin), style=ft.ButtonStyle(color=ft.Colors.PURPLE_200)),
                                    mensagem_alterar_senha_admin
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        page.update()

    # --- Inicia o aplicativo na tela de login ---
    mostrar_tela_login(None)


if __name__ == "__main__":
    # IMPORTANTE: Você precisa instalar a biblioteca 'psycopg2-binary':
    # pip install psycopg2-binary
    # Certifique-se de que seu banco de dados PostgreSQL externo esteja acessível e que as credenciais estejam corretas.
   ft.app(target=main, view=ft.WEB_BROWSER, assets_dir="assets", port=8550)

