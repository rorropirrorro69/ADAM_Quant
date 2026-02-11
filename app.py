import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from google.oauth2.service_account import Credentials
import gspread

# --- 1. CONFIGURACIÓN E INICIO ---
st.set_page_config(page_title="ADAM Quant - Alpha Terminal", layout="wide", page_icon="🛡️")

# Estilos CSS
st.markdown("""
    <style>
    .metric-container { background-color: #1E1E1E; border-radius: 10px; padding: 15px; border: 1px solid #333; }
    .stProgress > div > div > div > div { background-color: #00FF88; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #00FF88; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ROBUSTA (Manual) ---
# Esta función arregla la llave si Streamlit la rompe
@st.cache_resource
def connect_to_sheets_robust():
    try:
        # Recuperamos el diccionario de secrets
        # Nota: Usamos st.secrets normal, pero procesamos la llave
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("❌ No se encontraron los Secrets. Revisa la configuración en la nube.")
            st.stop()
            
        secrets = dict(st.secrets["connections"]["gsheets"])
        
        # EL FIX MÁGICO: Reemplazar \\n por \n real
        if "\\n" in secrets["private_key"]:
            secrets["private_key"] = secrets["private_key"].replace("\\n", "\n")
            
        # Definimos los permisos necesarios
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Creamos credenciales manuales
        creds = Credentials.from_service_account_info(secrets, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Abrimos el archivo
        spreadsheet_url = secrets["spreadsheet"]
        sh = client.open_by_url(spreadsheet_url)
        return sh
        
    except Exception as e:
        st.error(f"❌ Error Fatal de Conexión: {e}")
        st.stop()

# Inicializamos la conexión
sh = connect_to_sheets_robust()

# --- 3. FUNCIONES DE DATOS (Usando gspread directo) ---
def get_data(worksheet_name):
    try:
        worksheet = sh.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except gspread.exceptions.WorksheetNotFound:
        # Si no existe, devolvemos vacío con columnas esperadas
        if worksheet_name == "users":
            return pd.DataFrame(columns=["username", "password"])
        return pd.DataFrame(columns=["Date", "Symbol", "P&L", "Setup", "Side", "R_Multiple", "Mistakes", "username"])
    except Exception as e:
        st.error(f"Error leyendo {worksheet_name}: {e}")
        return pd.DataFrame()

def save_row(worksheet_name, row_data_dict):
    try:
        worksheet = sh.worksheet(worksheet_name)
        # Convertimos el dict a una lista de valores en el orden correcto
        # Esto requiere leer los headers primero para asegurar el orden
        headers = worksheet.row_values(1)
        
        if not headers:
            # Si está vacía, creamos headers
            headers = list(row_data_dict.keys())
            worksheet.append_row(headers)
            
        row_values = [row_data_dict.get(h, "") for h in headers]
        worksheet.append_row(row_values)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- 4. CONSTANTES ---
STARTING_BALANCE = 50000.0
MAX_DRAWDOWN_LIMIT = 2500.0
GOAL_BALANCE = 54100.0

# --- 5. LÓGICA DE USUARIO ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🛡️ ADAM Quant | Alpha Login")
    
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Crear Cuenta"])
    
    with tab1:
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                users = get_data("users")
                # Asegurar que sea string para comparar
                users['password'] = users['password'].astype(str)
                
                if not users.empty and u in users["username"].values:
                    real_pass = users[users["username"] == u]["password"].values[0]
                    if real_pass == p:
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta")
                else:
                    st.error("Usuario no encontrado")

    with tab2:
        with st.form("register"):
            new_u = st.text_input("Nuevo Usuario")
            new_p = st.text_input("Nueva Contraseña", type="password")
            if st.form_submit_button("Crear"):
                users = get_data("users")
                if not users.empty and new_u in users["username"].values:
                    st.warning("Usuario ya existe")
                else:
                    save_row("users", {"username": new_u, "password": new_p})
                    st.success("Cuenta creada. Inicia sesión.")

else:
    # --- DASHBOARD LOGUEADO ---
    username = st.session_state.username
    st.sidebar.title(f"👤 {username}")
    nav = st.sidebar.radio("Menú", ["Dashboard", "Registrar Trade", "Salir"])

    if nav == "Salir":
        st.session_state.logged_in = False
        st.rerun()

    if nav == "Registrar Trade":
        st.subheader("📝 Registrar Operación")
        with st.form("trade"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Fecha", date.today())
            sym = c1.selectbox("Symbol", ["NQ", "ES", "MNQ", "MES", "GC", "BTC"])
            side = c1.selectbox("Side", ["Long", "Short"])
            
            pnl = c2.number_input("P&L ($)", step=10.0)
            rm = c2.number_input("R-Multiple", value=1.0)
            setup = c2.text_input("Setup", "Manual")
            mistakes = st.text_area("Notas")
            
            if st.form_submit_button("Guardar"):
                new_trade = {
                    "Date": str(d),
                    "Symbol": sym,
                    "P&L": pnl,
                    "Setup": setup,
                    "Side": side,
                    "R_Multiple": rm,
                    "Mistakes": mistakes,
                    "username": username
                }
                if save_row("trades", new_trade):
                    st.success("✅ Trade Guardado")

    if nav == "Dashboard":
        st.title(f"🛡️ Terminal: {username}")
        df = get_data("trades")
        
        if not df.empty and "username" in df.columns:
            df = df[df["username"] == username].copy()
            if not df.empty:
                df['P&L'] = pd.to_numeric(df['P&L'])
                net = df['P&L'].sum()
                equity = STARTING_BALANCE + net
                
                # Progress
                target = GOAL_BALANCE - STARTING_BALANCE
                prog = min(1.0, max(0.0, net / target))
                
                st.write(f"### Meta Payout: ${GOAL_BALANCE:,.0f}")
                st.progress(prog)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Balance", f"${equity:,.2f}", f"{net:,.2f}")
                c2.metric("Trades", len(df))
                
                wins = df[df['P&L'] > 0]
                wr = (len(wins)/len(df))*100
                c3.metric("Win Rate", f"{wr:.1f}%")
                
                st.write("---")
                st.dataframe(df.sort_index(ascending=False))
            else:
                st.info("Sin trades registrados.")
        else:
            st.info("Base de datos vacía.")
