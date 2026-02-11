import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
import calendar
from datetime import datetime, date

# --- CONFIGURACIÓN DE UI ---
st.set_page_config(page_title="ADAM Quant - Alpha Terminal", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    .metric-container {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stProgress > div > div > div > div {
        background-color: #00FF88;
    }
    </style>
    """, unsafe_allow_html=True)

USER_DB = 'users.json'
DB_FOLDER = 'user_data/'
if not os.path.exists(DB_FOLDER): os.makedirs(DB_FOLDER)

# --- CONSTANTES DE CUENTA ---
STARTING_BALANCE = 50000.0
MAX_DRAWDOWN_LIMIT = 2500.0
LIQUIDATION_THRESHOLD = STARTING_BALANCE - MAX_DRAWDOWN_LIMIT

# --- LÓGICA DE DATOS Y USUARIOS ---
def load_users():
    if os.path.exists(USER_DB):
        with open(USER_DB, 'r') as f: return json.load(f)
    return {"admin": "admin123"}

def save_users(users):
    with open(USER_DB, 'w') as f: json.dump(users, f)

def get_user_file(username): return f"{DB_FOLDER}{username}_journal.csv"

# --- APP PRINCIPAL ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🛡️ ADAM Quant - Alpha Terminal")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Crear Cuenta"])
    with tab1:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            users = load_users()
            if u in users and users[u] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
    with tab2:
        new_u = st.text_input("Nuevo Usuario")
        new_p = st.text_input("Nueva Contraseña", type="password")
        if st.button("Registrar"):
            users = load_users()
            users[new_u] = new_p
            save_users(users)
            st.success("Cuenta creada.")
else:
    username = st.session_state.username
    user_file = get_user_file(username)

    def load_user_data():
        if os.path.exists(user_file):
            df = pd.read_csv(user_file)
            df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
            return df.dropna(subset=['Date'])
        return pd.DataFrame(columns=['Date', 'Symbol', 'P&L', 'Setup', 'Side', 'R_Multiple', 'Mistakes'])

    # Sidebar
    st.sidebar.title(f"👤 {username}")
    nav = st.sidebar.radio("Navegación", ["Dashboard", "Registrar Trade", "Cerrar Sesión"])

    if nav == "Cerrar Sesión":
        st.session_state.logged_in = False
        st.rerun()

    if nav == "Registrar Trade":
        st.subheader("📝 Nuevo Registro")
        df = load_user_data()
        with st.form("trade_form"):
            col1, col2 = st.columns(2)
            with col1:
                d = st.date_input("Fecha", date.today())
                sym = st.selectbox("Símbolo", ["NQ", "ES", "MNQ", "MES", "BTC", "GOLD"])
                side = st.selectbox("Lado", ["Long", "Short"])
            with col2:
                pnl = st.number_input("P&L ($)", step=50.0)
                rm = st.number_input("R-Multiple", step=0.1, value=1.0)
                setup = st.text_input("Setup", value="Manual")
            
            if st.form_submit_button("Guardar Trade"):
                new_row = pd.DataFrame([[pd.to_datetime(d), sym, pnl, setup, side, rm, "None"]], columns=df.columns)
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(user_file, index=False)
                st.success("Trade registrado exitosamente.")

    if nav == "Dashboard":
        st.title(f"🛡️ Terminal Pro: {username}")
        df = load_user_data()
        
        if not df.empty:
            # --- CÁLCULOS DE MÉTRICAS ---
            df = df.sort_values('Date')
            net_pnl = df['P&L'].sum()
            current_balance = STARTING_BALANCE + net_pnl
            
            # Cálculo de Drawdown Actual (desde el pico de equidad)
            df['Cumulative_PnL'] = df['P&L'].cumsum()
            df['Equity'] = STARTING_BALANCE + df['Cumulative_PnL']
            peak = df['Equity'].cummax()
            current_dd = peak.iloc[-1] - current_balance
            dd_pct_of_limit = min(1.0, current_dd / MAX_DRAWDOWN_LIMIT)

            trade_win = (len(df[df['P&L'] > 0]) / len(df)) * 100
            
            # Profit Factor
            gains = df[df['P&L'] > 0]['P&L'].sum()
            losses = abs(df[df['P&L'] < 0]['P&L'].sum())
            pf = gains / losses if losses > 0 else 1.0
            
            # 1. FILA DE MÉTRICAS (KPIs)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Balance Actual", f"${current_balance:,.2f}", delta=f"${net_pnl:,.2f} Total")
                st.caption(f"Balance Inicial: ${STARTING_BALANCE:,.0f}")
            
            with c2:
                fig_tw = go.Figure(go.Indicator(mode="gauge+number", value=trade_win, number={'suffix': "%"},
                    gauge={'bar': {'color': "#00FF88"}, 'axis': {'range': [0, 100]}},
                    title={'text': "Win Rate", 'font': {'size': 14}}))
                fig_tw.update_layout(height=150, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
                st.plotly_chart(fig_tw, use_container_width=True)

            with c3:
                dd_color = "#00FF88" if current_dd < (MAX_DRAWDOWN_LIMIT * 0.5) else "#FFCC00" if current_dd < (MAX_DRAWDOWN_LIMIT * 0.8) else "#FF4B4B"
                st.write("**Uso de Drawdown Máx.**")
                st.markdown(f"""
                    <div style="width: 100%; background-color: #444; border-radius: 5px; height: 25px; margin-bottom:5px;">
                        <div style="width: {dd_pct_of_limit*100}%; background-color: {dd_color}; height: 100%; border-radius: 5px;"></div>
                    </div>
                """, unsafe_allow_html=True)
                st.caption(f"DD Actual: ${current_dd:,.2f} / Límite: ${MAX_DRAWDOWN_LIMIT:,.0f}")
            
            with c4:
                avg_w = df[df['P&L'] > 0]['P&L'].mean() if not df[df['P&L'] > 0].empty else 0
                avg_l = abs(df[df['P&L'] < 0]['P&L'].mean()) if not df[df['P&L'] < 0].empty else 1
                ratio = avg_w / (avg_w + avg_l) if (avg_w + avg_l) > 0 else 0.5
                st.write("**Avg Win vs Loss**")
                st.markdown(f"""
                    <div style="width: 100%; background-color: #444; border-radius: 5px; height: 15px; display: flex;">
                        <div style="width: {ratio*100}%; background-color: #00FF88; height: 100%; border-radius: 5px 0 0 5px;"></div>
                        <div style="width: {(1-ratio)*100}%; background-color: #FF4B4B; height: 100%; border-radius: 0 5px 5px 0;"></div>
                    </div>
                """, unsafe_allow_html=True)
                st.caption(f"W: ${avg_w:,.0f} / L: ${avg_l:,.0f}")

            # 2. MILESTONE SECTION
            st.divider()
            target_val = 54100
            target_profit_needed = target_val - STARTING_BALANCE
            progress_pct = min(1.0, max(0.0, net_pnl / target_profit_needed)) if net_pnl > 0 else 0
            
            col_target1, col_target2 = st.columns([2, 1])
            with col_target1:
                st.subheader(f"🎯 Milestone a Objetivo: ${target_val:,.0f}")
                st.progress(progress_pct)
                st.write(f"Progreso Profit: **{progress_pct*100:.2f}%** | Faltan: **${max(0, target_val - current_balance):,.2f}**")
            
            with col_target2:
                trades_to_goal = int((target_val - current_balance) / avg_w) if avg_w > 0 and (target_val > current_balance) else 0
                st.metric("Trades Est. para Meta", f"~{trades_to_goal}", help="Basado en tu promedio de ganancia.")

            # 3. GRÁFICOS INTERMEDIOS
            col_radar, col_pnl_chart = st.columns([1, 1])
            with col_radar:
                st.subheader("🎯 Zella Score")
                categories = ['Win %', 'Profit Factor', 'Risk Reward', 'DD Control', 'Consistency']
                dd_score = max(0, 100 - (dd_pct_of_limit * 100))
                scores = [trade_win, min(100, pf*20), (avg_w/avg_l)*20, dd_score, 75] 
                fig_radar = go.Figure(data=go.Scatterpolar(r=scores, theta=categories, fill='toself', line_color='#00FF88'))
                fig_radar.update_layout(polar=dict(radialaxis=dict(visible=False)), template="plotly_dark", height=350)
                st.plotly_chart(fig_radar, use_container_width=True)

            with col_pnl_chart:
                st.subheader("📈 Curva de Equidad")
                # Punto de inicio para el gráfico
                initial_point = pd.DataFrame({'Date': [df['Date'].min()], 'Equity': [STARTING_BALANCE]})
                plot_df = pd.concat([initial_point, df[['Date', 'Equity']]]).sort_values('Date')
                
                fig_equity = go.Figure(go.Scatter(x=plot_df['Date'], y=plot_df['Equity'], fill='tozeroy', line_color='#00FF88', name="Equity"))
                fig_equity.add_hline(y=LIQUIDATION_THRESHOLD, line_dash="dash", line_color="red", annotation_text="Límite Drawdown")
                fig_equity.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,b=0,t=20))
                st.plotly_chart(fig_equity, use_container_width=True)

            # 4. CALENDARIO
            st.divider()
            st.subheader("📅 Calendario Mensual")
            daily_map = df.groupby(df['Date'].dt.date)['P&L'].sum().to_dict()
            cal = calendar.monthcalendar(datetime.now().year, datetime.now().month)
            for week in cal:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day != 0:
                        d_obj = date(datetime.now().year, datetime.now().month, day)
                        val = daily_map.get(d_obj, 0)
                        color = "#00FF88" if val > 0 else "#FF4B4B" if val < 0 else "#444"
                        cols[i].markdown(f"<div style='border:1px solid #333; padding:5px; text-align:center; border-radius:5px;'>{day}<br><b style='color:{color}'>${val:,.0f}</b></div>", unsafe_allow_html=True)

            # 5. REGISTRO DETALLADO
            st.divider()
            st.subheader("📜 Bitácora Histórica")
            df_log = df.sort_values(by='Date', ascending=False).copy()
            def color_pnl(val):
                color = '#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_log[['Date', 'Symbol', 'Side', 'P&L', 'R_Multiple', 'Setup']].style.applymap(color_pnl, subset=['P&L'])
                .format({"P&L": "${:,.2f}", "R_Multiple": "{:.2f}R"}),
                use_container_width=True, hide_index=True
            )
            
        else:
            st.info("No hay datos suficientes. Registra tu primer trade para activar la terminal.")
