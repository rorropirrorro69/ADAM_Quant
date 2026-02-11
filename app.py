import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.graph_objects as go
import calendar
from datetime import datetime, date

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="ADAM Quant - Alpha Terminal", layout="wide", page_icon="🛡️")

# Estilos CSS para apariencia profesional
st.markdown("""
    <style>
    .metric-container {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #333;
    }
    .stProgress > div > div > div > div {
        background-color: #00FF88;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        color: #00FF88;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 3. CONSTANTES DEL PROYECTO ---
STARTING_BALANCE = 50000.0
MAX_DRAWDOWN_LIMIT = 2500.0
GOAL_BALANCE = 54100.0  # Meta para el payout
LIQUIDATION_THRESHOLD = STARTING_BALANCE - MAX_DRAWDOWN_LIMIT

# --- 4. FUNCIONES DE GESTIÓN DE DATOS ---
def get_all_users():
    """Carga la lista de usuarios desde la hoja 'users'."""
    try:
        df = conn.read(worksheet="users", ttl=0)
        return df if not df.empty else pd.DataFrame(columns=["username", "password"])
    except:
        return pd.DataFrame(columns=["username", "password"])

def get_user_trades(username):
    """Carga los trades de un usuario específico desde la hoja 'trades'."""
    try:
        df = conn.read(worksheet="trades", ttl=0)
        if not df.empty and "username" in df.columns:
            # Filtrar por usuario y asegurar formato de fecha
            df_user = df[df["username"] == username].copy()
            df_user['Date'] = pd.to_datetime(df_user['Date'])
            return df_user
        # Estructura vacía si no hay datos
        return pd.DataFrame(columns=['Date', 'Symbol', 'P&L', 'Setup', 'Side', 'R_Multiple', 'Mistakes', 'username'])
    except:
        return pd.DataFrame(columns=['Date', 'Symbol', 'P&L', 'Setup', 'Side', 'R_Multiple', 'Mistakes', 'username'])

# --- 5. LÓGICA DE AUTENTICACIÓN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🛡️ ADAM Quant | Alpha Login")
    
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Crear Cuenta"])
    
    with tab1:
        with st.form("login_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar")
            
            if submitted:
                users_df = get_all_users()
                if not users_df.empty and u in users_df["username"].values:
                    stored_pass = users_df[users_df["username"] == u]["password"].values[0]
                    # Convertimos a string para asegurar comparación
                    if str(stored_pass) == str(p):
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
                else:
                    st.error("Usuario no encontrado.")

    with tab2:
        with st.form("register_form"):
            new_u = st.text_input("Nuevo Usuario")
            new_p = st.text_input("Nueva Contraseña", type="password")
            reg_submitted = st.form_submit_button("Registrar")
            
            if reg_submitted:
                if new_u and new_p:
                    users_df = get_all_users()
                    if not users_df.empty and new_u in users_df["username"].values:
                        st.warning("El usuario ya existe.")
                    else:
                        new_user_row = pd.DataFrame([{"username": new_u, "password": new_p}])
                        # Concatenar y guardar
                        updated_users = pd.concat([users_df, new_user_row], ignore_index=True)
                        conn.update(worksheet="users", data=updated_users)
                        st.success("¡Cuenta creada! Ve a la pestaña de Iniciar Sesión.")
                else:
                    st.warning("Por favor llena todos los campos.")

# --- 6. APLICACIÓN PRINCIPAL (DASHBOARD) ---
else:
    username = st.session_state.username
    
    # Sidebar
    st.sidebar.title(f"👤 Trader: {username}")
    st.sidebar.markdown("---")
    nav = st.sidebar.radio("Menú", ["Dashboard Pro", "Registrar Trade", "Cerrar Sesión"])

    if nav == "Cerrar Sesión":
        st.session_state.logged_in = False
        st.rerun()

    # --- VISTA: REGISTRAR TRADE ---
    if nav == "Registrar Trade":
        st.subheader("📝 Bitácora de Operaciones")
        st.info("Registra tus operaciones para alimentar el algoritmo de análisis.")
        
        with st.form("trade_form"):
            col1, col2 = st.columns(2)
            with col1:
                d = st.date_input("Fecha", date.today())
                sym = st.selectbox("Instrumento", ["NQ", "ES", "MNQ", "MES", "BTC", "GOLD", "CL"])
                side = st.selectbox("Dirección", ["Long", "Short"])
            with col2:
                pnl = st.number_input("P&L ($)", step=50.0, format="%.2f")
                rm = st.number_input("R-Multiple", step=0.1, value=1.0)
                setup = st.text_input("Setup / Estrategia", value="Manual")
            
            notes = st.text_area("Notas / Errores", "Ninguno")
            
            if st.form_submit_button("💾 Guardar Trade en Nube"):
                try:
                    # Cargar trades existentes
                    all_trades = conn.read(worksheet="trades", ttl=0)
                    
                    # Crear nuevo registro
                    new_trade = pd.DataFrame([{
                        "Date": d.strftime('%Y-%m-%d'),
                        "Symbol": sym,
                        "P&L": float(pnl),
                        "Setup": setup,
                        "Side": side,
                        "R_Multiple": float(rm),
                        "Mistakes": notes,
                        "username": username
                    }])
                    
                    # Guardar
                    updated_trades = pd.concat([all_trades, new_trade], ignore_index=True)
                    conn.update(worksheet="trades", data=updated_trades)
                    st.success("✅ Trade sincronizado exitosamente con Google Sheets.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error guardando: {e}")

    # --- VISTA: DASHBOARD ---
    if nav == "Dashboard Pro":
        st.title(f"🛡️ Terminal Alpha: {username}")
        df = get_user_trades(username)
        
        if not df.empty:
            # Procesamiento de Datos
            df = df.sort_values('Date')
            net_pnl = df['P&L'].sum()
            current_balance = STARTING_BALANCE + net_pnl
            
            # Cálculos de Drawdown
            df['Cumulative_PnL'] = df['P&L'].cumsum()
            df['Equity'] = STARTING_BALANCE + df['Cumulative_PnL']
            peak = df['Equity'].cummax()
            current_dd = peak.iloc[-1] - current_balance
            dd_pct_of_limit = min(1.0, current_dd / MAX_DRAWDOWN_LIMIT) if MAX_DRAWDOWN_LIMIT > 0 else 0

            # KPIs Avanzados
            wins = df[df['P&L'] > 0]
            losses = df[df['P&L'] < 0]
            win_rate = (len(wins) / len(df)) * 100
            
            avg_win = wins['P&L'].mean() if not wins.empty else 0
            avg_loss = abs(losses['P&L'].mean()) if not losses.empty else 0
            profit_factor = (wins['P&L'].sum() / abs(losses['P&L'].sum())) if not losses.empty else 0
            
            # --- SECCIÓN 1: METAS Y PROGRESO ---
            st.markdown("### 🎯 Objetivo de Payout")
            profit_target = GOAL_BALANCE - STARTING_BALANCE
            progress = min(1.0, max(0.0, net_pnl / profit_target)) if profit_target > 0 else 0
            
            col_g1, col_g2 = st.columns([3, 1])
            with col_g1:
                st.progress(progress)
                st.caption(f"Progreso: ${net_pnl:,.2f} / Meta: ${profit_target:,.2f} (Restante: ${max(0, profit_target - net_pnl):,.2f})")
            with col_g2:
                 st.metric("Distancia a Meta", f"{progress*100:.1f}%")

            # --- SECCIÓN 2: KPIs PRINCIPALES ---
            st.markdown("---")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            with kpi1:
                st.metric("Balance Total", f"${current_balance:,.2f}", delta=f"${net_pnl:,.2f}")
            with kpi2:
                st.metric("Win Rate", f"{win_rate:.1f}%", delta="Objetivo: 60%")
            with kpi3:
                st.metric("Profit Factor", f"{profit_factor:.2f}", delta="Objetivo: >1.5")
            with kpi4:
                dd_color = "normal" if current_dd < 1500 else "inverse"
                st.metric("Drawdown Actual", f"-${current_dd:,.2f}", delta=f"Límite: ${MAX_DRAWDOWN_LIMIT}", delta_color=dd_color)

            # --- SECCIÓN 3: GRÁFICOS ---
            col_chart1, col_chart2 = st.columns([2, 1])
            
            with col_chart1:
                st.subheader("📈 Curva de Equidad")
                fig_equity = go.Figure()
                fig_equity.add_trace(go.Scatter(x=df['Date'], y=df['Equity'], mode='lines', name='Equity', fill='tozeroy', line=dict(color='#00FF88', width=2)))
                fig_equity.add_hline(y=LIQUIDATION_THRESHOLD, line_dash="dash", line_color="#FF4B4B", annotation_text="Liquidation Lvl")
                fig_equity.add_hline(y=GOAL_BALANCE, line_dash="dash", line_color="#00CCFF", annotation_text="Payout Goal")
                fig_equity.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=350, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig_equity, use_container_width=True)

            with col_chart2:
                st.subheader("📊 Zella Score")
                # Cálculo simple de un "Score" de trader
                score_consistency = 100 if len(df) > 10 else len(df)*10
                score_profit = min(100, profit_factor * 30)
                score_risk = max(0, 100 - (dd_pct_of_limit * 100))
                
                categories = ['Win Rate', 'Profit Factor', 'Risk Mgmt', 'Consistency', 'Momentum']
                values = [win_rate, score_profit, score_risk, score_consistency, 80]
                
                fig_radar = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', line_color='#00CCFF'))
                fig_radar.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 100])), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=350, margin=dict(l=40,r=40,t=30,b=30))
                st.plotly_chart(fig_radar, use_container_width=True)

            # --- SECCIÓN 4: HISTORIAL ---
            st.markdown("---")
            st.subheader("📜 Historial de Operaciones")
            
            # Formato condicional para el dataframe
            def color_pnl(val):
                color = '#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'
                return f'color: {color}'

            display_df = df[['Date', 'Symbol', 'Side', 'Setup', 'P&L', 'R_Multiple', 'Mistakes']].sort_values('Date', ascending=False)
            st.dataframe(
                display_df.style.map(color_pnl, subset=['P&L']).format({"P&L": "${:,.2f}", "Date": "{:%Y-%m-%d}"}),
                use_container_width=True,
                hide_index=True
            )
            
        else:
            st.info("👋 ¡Bienvenido! Aún no tienes trades registrados. Ve al menú lateral para ingresar tu primera operación.")
