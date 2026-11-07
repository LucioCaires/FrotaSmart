import hmac
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("FROTASMART_DATA_DIR", APP_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "frotasmart.db"

st.set_page_config(page_title="FrotaSmart | Gestão de frotas", page_icon="🚚", layout="wide")

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL UNIQUE,
                model TEXT NOT NULL,
                year INTEGER,
                fuel_type TEXT NOT NULL DEFAULT 'Diesel',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fuelings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                odometer REAL NOT NULL,
                liters REAL NOT NULL,
                total_cost REAL NOT NULL,
                station TEXT,
                notes TEXT,
                FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
            )
        """)

def query_df(sql, params=()):
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def load_demo_data():
    """Add clearly fictional sample records to make the portfolio demo useful."""
    with connect() as conn:
        vehicle_count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        fueling_count = conn.execute("SELECT COUNT(*) FROM fuelings").fetchone()[0]
        if vehicle_count or fueling_count:
            return False

        created_at = datetime.now().isoformat(timespec="seconds")
        vehicles_to_add = [
            ("ABC1D23", "Van de entregas", 2022, "Diesel", 1, created_at),
            ("EFG4H56", "Caminhão leve", 2021, "Diesel", 1, created_at),
            ("JKL7M89", "Carro de apoio", 2023, "Flex", 1, created_at),
        ]
        conn.executemany(
            "INSERT INTO vehicles (plate, model, year, fuel_type, active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            vehicles_to_add,
        )
        vehicle_ids = dict(conn.execute(
            "SELECT plate, id FROM vehicles WHERE plate IN ('ABC1D23', 'EFG4H56', 'JKL7M89')"
        ))
        today = date.today()
        fuelings_to_add = [
            (vehicle_ids["ABC1D23"], (today - timedelta(days=18)).isoformat(), 42100, 55, 330, "Posto Central", "Dado fictício de demonstração"),
            (vehicle_ids["ABC1D23"], (today - timedelta(days=9)).isoformat(), 42520, 58, 348, "Posto Central", "Dado fictício de demonstração"),
            (vehicle_ids["ABC1D23"], today.isoformat(), 42910, 52, 312, "Posto Norte", "Dado fictício de demonstração"),
            (vehicle_ids["EFG4H56"], (today - timedelta(days=13)).isoformat(), 78900, 72, 432, "Auto Posto Sul", "Dado fictício de demonstração"),
            (vehicle_ids["EFG4H56"], (today - timedelta(days=2)).isoformat(), 79380, 68, 408, "Auto Posto Sul", "Dado fictício de demonstração"),
            (vehicle_ids["JKL7M89"], (today - timedelta(days=5)).isoformat(), 18750, 42, 252, "Posto Avenida", "Dado fictício de demonstração"),
        ]
        conn.executemany(
            "INSERT INTO fuelings (vehicle_id, date, odometer, liters, total_cost, station, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            fuelings_to_add,
        )
    return True

def money(value):
    return "R$ " + f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def require_access():
    expected_password = os.environ.get("FROTASMART_PASSWORD", "")
    if not expected_password:
        if os.environ.get("FROTASMART_ENV") == "production":
            st.error("O administrador precisa configurar a senha de acesso do FrotaSmart.")
            return False
        return True
    if st.session_state.get("frotasmart_authenticated"):
        return True

    st.title("🚚 FrotaSmart")
    st.subheader("Acesso ao aplicativo")
    with st.form("login_form"):
        entered_password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted:
        if hmac.compare_digest(entered_password, expected_password):
            st.session_state["frotasmart_authenticated"] = True
            st.rerun()
        st.error("Senha incorreta.")
    return False

if not require_access():
    st.stop()

init_db()

st.title("🚚 FrotaSmart")
st.caption("Gestão de veículos, abastecimentos e custos operacionais")
st.markdown("""
<style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {background: rgba(120,120,120,.07); padding: 14px; border-radius: 12px;}
    div[data-testid="stMetric"] label {font-size: .88rem;}
    section[data-testid="stSidebar"] {border-right: 1px solid rgba(120,120,120,.15);}
    @media (max-width: 700px) {
        .block-container {padding: 1rem .8rem 1.5rem;}
        div[data-testid="stHorizontalBlock"] {flex-wrap: wrap; gap: .65rem;}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 1 1 100% !important; min-width: 100% !important; width: 100% !important;
        }
        div[data-testid="stMetric"] {padding: 10px 12px;}
    }
</style>
""", unsafe_allow_html=True)

vehicles = query_df("SELECT * FROM vehicles ORDER BY plate")
fuelings = query_df("""
    SELECT f.id, f.vehicle_id, v.plate, v.model, f.date, f.odometer,
           f.liters, f.total_cost, f.station, f.notes
    FROM fuelings f JOIN vehicles v ON v.id = f.vehicle_id
    ORDER BY f.date DESC, f.id DESC
""")

with st.sidebar:
    st.header("Navegação")
    page = st.radio("Escolha uma seção", [
        "Painel", "Veículos", "Abastecimentos", "Relatórios"
    ])
    st.divider()
    st.caption("FrotaSmart • Projeto de portfólio")
    st.caption("Versão de portfólio 1.2")
    if os.environ.get("FROTASMART_PASSWORD") and st.button("Sair", use_container_width=True):
        st.session_state.pop("frotasmart_authenticated", None)
        st.rerun()
    st.divider()
    if vehicles.empty and fuelings.empty:
        st.caption("Quer visualizar o painel preenchido?")
        if st.button("Carregar dados de demonstração", use_container_width=True):
            if load_demo_data():
                st.success("Dados fictícios carregados.")
                st.rerun()
            else:
                st.info("Já existem registros. Os dados não foram alterados.")

if page == "Painel":
    st.subheader("Visão geral")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Veículos cadastrados", int(len(vehicles)))
    c2.metric("Abastecimentos", int(len(fuelings)))
    c3.metric("Gasto registrado", money(fuelings["total_cost"].sum() if not fuelings.empty else 0))
    c4.metric("Litros abastecidos", f'{fuelings["liters"].sum():,.1f} L'.replace(",", "X").replace(".", ",").replace("X", "."))
    st.caption("Indicadores calculados a partir dos registros salvos no aplicativo.")

    st.markdown("### Últimos abastecimentos")
    if fuelings.empty:
        st.info("Ainda não há abastecimentos. Cadastre um veículo e registre o primeiro abastecimento para ver os indicadores.")
    else:
        recent = fuelings[["date", "plate", "model", "odometer", "liters", "total_cost", "station"]].head(8).copy()
        recent["total_cost"] = recent["total_cost"].map(money)
        recent.columns = ["Data", "Placa", "Veículo", "Odômetro (km)", "Litros", "Valor", "Posto"]
        st.dataframe(recent, use_container_width=True, hide_index=True)

    if not fuelings.empty:
        st.markdown("### Gastos por veículo")
        costs = fuelings.groupby("plate", as_index=False)["total_cost"].sum().sort_values("total_cost", ascending=False)
        costs.columns = ["Placa", "Gasto total (R$)"]
        st.bar_chart(costs.set_index("Placa"))

elif page == "Veículos":
    st.subheader("Cadastro de veículos")
    st.caption("Mantenha os dados dos veículos da frota organizados em um só lugar.")
    with st.form("vehicle_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        plate = col1.text_input("Placa *", placeholder="ABC1D23").strip().upper().replace(" ", "")
        model = col2.text_input("Modelo / descrição *", placeholder="Ex.: Caminhão toco")
        year = col3.number_input("Ano", min_value=1950, max_value=2100, value=date.today().year, step=1)
        col4, col5 = st.columns(2)
        fuel_type = col4.selectbox("Combustível", ["Diesel", "Gasolina", "Etanol", "Flex", "Elétrico", "Outro"])
        active = col5.selectbox("Situação", ["Ativo", "Inativo"])
        submitted = st.form_submit_button("Cadastrar veículo", type="primary")
        if submitted:
            if not plate or not model.strip():
                st.error("Preencha a placa e a descrição do veículo.")
            else:
                try:
                    with connect() as conn:
                        conn.execute(
                            "INSERT INTO vehicles (plate, model, year, fuel_type, active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (plate, model.strip(), int(year), fuel_type, 1 if active == "Ativo" else 0, datetime.now().isoformat(timespec="seconds"))
                        )
                    st.success(f"Veículo {plate} cadastrado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Essa placa já está cadastrada.")

    st.markdown("### Veículos cadastrados")
    if vehicles.empty:
        st.info("Nenhum veículo cadastrado ainda.")
    else:
        display = vehicles[["plate", "model", "year", "fuel_type", "active"]].copy()
        display["active"] = display["active"].map({1: "Ativo", 0: "Inativo"})
        display.columns = ["Placa", "Modelo", "Ano", "Combustível", "Situação"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        with st.expander("Excluir um veículo"):
            st.warning("A exclusão só é permitida quando o veículo não tem abastecimentos registrados.")
            choices = {f'{r.plate} — {r.model}': int(r.id) for r in vehicles.itertuples()}
            selected_label = st.selectbox("Veículo", list(choices.keys()))
            if st.button("Excluir veículo selecionado"):
                vid = choices[selected_label]
                count = query_df("SELECT COUNT(*) AS n FROM fuelings WHERE vehicle_id = ?", (vid,)).iloc[0]["n"]
                if count:
                    st.error("Este veículo tem abastecimentos. Para preservar o histórico, não é possível excluí-lo.")
                else:
                    with connect() as conn:
                        conn.execute("DELETE FROM vehicles WHERE id = ?", (vid,))
                    st.success("Veículo excluído.")
                    st.rerun()

elif page == "Abastecimentos":
    st.subheader("Registro de abastecimento")
    st.caption("Registre data, quilometragem, litros e valor para acompanhar os custos.")
    if vehicles.empty:
        st.warning("Cadastre um veículo antes de registrar abastecimentos.")
    else:
        options = {f'{r.plate} — {r.model}': int(r.id) for r in vehicles.itertuples()}
        with st.form("fuel_form", clear_on_submit=True):
            selected = st.selectbox("Veículo *", list(options.keys()))
            c1, c2 = st.columns(2)
            fuel_date = c1.date_input("Data do abastecimento", value=date.today())
            odometer = c2.number_input("Quilometragem atual (km)", min_value=0.0, step=1.0)
            c3, c4 = st.columns(2)
            liters = c3.number_input("Litros abastecidos", min_value=0.01, step=1.0, format="%.2f")
            total_cost = c4.number_input("Valor total (R$)", min_value=0.01, step=10.0, format="%.2f")
            station = st.text_input("Posto de combustível")
            notes = st.text_input("Observações")
            submitted = st.form_submit_button("Salvar abastecimento", type="primary")
            if submitted:
                vid = options[selected]
                history = query_df(
                    "SELECT date, odometer FROM fuelings WHERE vehicle_id = ? ORDER BY date, id", (vid,)
                )
                earlier = history[history["date"] <= fuel_date.isoformat()]
                later = history[history["date"] > fuel_date.isoformat()]
                previous = earlier["odometer"].max() if not earlier.empty else None
                next_reading = later["odometer"].min() if not later.empty else None
                if previous is not None and odometer < float(previous):
                    st.error(f"A quilometragem informada é menor que um registro nessa data ou anterior ({previous:,.0f} km). Confira o valor.")
                elif next_reading is not None and odometer > float(next_reading):
                    st.error(f"A quilometragem informada supera um registro posterior ({next_reading:,.0f} km). Confira a data ou o valor.")
                else:
                    with connect() as conn:
                        conn.execute("""
                            INSERT INTO fuelings (vehicle_id, date, odometer, liters, total_cost, station, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (vid, fuel_date.isoformat(), odometer, liters, total_cost, station.strip(), notes.strip()))
                    st.success("Abastecimento registrado!")
                    st.rerun()

    st.markdown("### Histórico de abastecimentos")
    if fuelings.empty:
        st.info("Nenhum abastecimento registrado.")
    else:
        display = fuelings[["date", "plate", "model", "odometer", "liters", "total_cost", "station", "notes"]].copy()
        display.columns = ["Data", "Placa", "Veículo", "Odômetro (km)", "Litros", "Valor (R$)", "Posto", "Observações"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        with st.expander("Excluir registro de abastecimento"):
            row_choices = {
                f'#{int(r.id)} — {r.date} — {r.plate} — {money(r.total_cost)}': int(r.id)
                for r in fuelings.itertuples()
            }
            chosen = st.selectbox("Registro", list(row_choices.keys()))
            if st.button("Excluir abastecimento selecionado"):
                with connect() as conn:
                    conn.execute("DELETE FROM fuelings WHERE id = ?", (row_choices[chosen],))
                st.success("Registro excluído.")
                st.rerun()

elif page == "Relatórios":
    st.subheader("Relatórios e exportação")
    st.caption("Escolha um período para analisar abastecimentos e baixar os registros em CSV.")
    if fuelings.empty:
        st.info("Registre abastecimentos para gerar relatórios.")
    else:
        min_date = pd.to_datetime(fuelings["date"]).min().date()
        max_date = pd.to_datetime(fuelings["date"]).max().date()
        col1, col2 = st.columns(2)
        start = col1.date_input("Data inicial", value=min_date)
        end = col2.date_input("Data final", value=max_date)
        if start > end:
            st.error("A data inicial não pode ser posterior à data final.")
        else:
            filtered = fuelings[
                (pd.to_datetime(fuelings["date"]).dt.date >= start) &
                (pd.to_datetime(fuelings["date"]).dt.date <= end)
            ].copy()
            c1, c2, c3 = st.columns(3)
            c1.metric("Gasto no período", money(filtered["total_cost"].sum()))
            c2.metric("Litros no período", f'{filtered["liters"].sum():.2f} L')
            c3.metric("Registros", int(len(filtered)))
            st.markdown("#### Despesas por veículo")
            if filtered.empty:
                st.info("Nenhum registro nesse período.")
            else:
                grouped = filtered.groupby(["plate", "model"], as_index=False).agg(
                    abastecimentos=("id", "count"),
                    litros=("liters", "sum"),
                    gasto=("total_cost", "sum")
                )
                grouped.columns = ["Placa", "Veículo", "Abastecimentos", "Litros", "Gasto (R$)"]
                st.dataframe(grouped, use_container_width=True, hide_index=True)
                st.bar_chart(grouped.set_index("Placa")["Gasto (R$)"])
            csv = filtered.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Baixar relatório CSV",
                data=csv,
                file_name=f"frotasmart_relatorio_{start}_{end}.csv",
                mime="text/csv"
            )

st.divider()
st.caption("FrotaSmart é um projeto demonstrativo de portfólio. Use dados fictícios durante testes.")

