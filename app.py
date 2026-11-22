"""Панель над kino.db (варіант PY-C4Q / PR06-C5R)."""

import sqlite3
from datetime import date
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

DB = Path(__file__).parent / "kino.db"

st.set_page_config(page_title="Кіно: панель (PY-C4Q)", layout="wide")


@st.cache_resource
def zyednannya() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@st.cache_data
def spysok_rezhyseriv() -> list[str]:
    df = pd.read_sql("SELECT DISTINCT director FROM films ORDER BY director", zyednannya())
    return ["Усі режисери"] + df["director"].tolist()


@st.cache_data
def spysok_filmiv() -> list[tuple[int, str, int]]:
    return zyednannya().execute("SELECT id, title, year FROM films ORDER BY title").fetchall()


@st.cache_data
def chytaty_filmy(
    rik_vid: int,
    rik_do: int,
    data_vid: str,
    data_do: str,
    rezhyser: str,
    min_tryvalist: int,
) -> pd.DataFrame:
    zapyt = """
    SELECT f.id,
           f.title AS nazva,
           f.year AS rik,
           f.director AS rezhyser,
           f.duration_min AS tryvalist_khv,
           COUNT(v.id) AS pereglyadiv,
           COALESCE(SUM(v.viewers), 0) AS glyadachiv,
           (SELECT COUNT(*) FROM awards a WHERE a.film_id = f.id) AS nagorod
    FROM films AS f
    LEFT JOIN views AS v
      ON v.film_id = f.id
     AND v.viewed_on BETWEEN ? AND ?
    WHERE f.year BETWEEN ? AND ?
      AND (? = 'Усі режисери' OR f.director = ?)
      AND (? = 0 OR f.duration_min >= ?)
    GROUP BY f.id
    ORDER BY glyadachiv DESC, f.title ASC
    """
    params = (
        data_vid,
        data_do,
        rik_vid,
        rik_do,
        rezhyser,
        rezhyser,
        min_tryvalist,
        min_tryvalist,
    )
    return pd.read_sql(zapyt, zyednannya(), params=params)


@st.cache_data
def chytaty_po_misyatsyakh(
    rik_vid: int,
    rik_do: int,
    data_vid: str,
    data_do: str,
    rezhyser: str,
    min_tryvalist: int,
) -> pd.DataFrame:
    zapyt = """
    SELECT substr(v.viewed_on, 1, 7) AS misyats,
           COUNT(v.id) AS pereglyadiv
    FROM views AS v
    JOIN films AS f ON f.id = v.film_id
    WHERE f.year BETWEEN ? AND ?
      AND v.viewed_on BETWEEN ? AND ?
      AND (? = 'Усі режисери' OR f.director = ?)
      AND (? = 0 OR f.duration_min >= ?)
    GROUP BY misyats
    ORDER BY misyats
    """
    params = (
        rik_vid,
        rik_do,
        data_vid,
        data_do,
        rezhyser,
        rezhyser,
        min_tryvalist,
        min_tryvalist,
    )
    return pd.read_sql(zapyt, zyednannya(), params=params)


st.title("Кіно: аналітична панель (варіант PY-C4Q / PR06-C5R)")

if "dodano_nagorod" not in st.session_state:
    st.session_state["dodano_nagorod"] = 0
if "ostannya_nagoroda" not in st.session_state:
    st.session_state["ostannya_nagoroda"] = "ще не додавалися у цій сесії"

with st.sidebar:
    st.header("Фільтри вибірки")
    rik_vid, rik_do = st.slider("Роки випуску фільму", 1920, 2025, (1930, 1969))

    diapazon_dat = st.date_input(
        "Діапазон дат переглядів",
        value=(date(2024, 1, 1), date(2025, 12, 31)),
        min_value=date(2024, 1, 1),
        max_value=date(2025, 12, 31),
    )
    if isinstance(diapazon_dat, tuple) and len(diapazon_dat) == 2:
        data_vid, data_do = diapazon_dat[0].isoformat(), diapazon_dat[1].isoformat()
    elif isinstance(diapazon_dat, tuple) and len(diapazon_dat) == 1:
        data_vid = data_do = diapazon_dat[0].isoformat()
    else:
        data_vid = data_do = diapazon_dat.isoformat()

    rezhyser = st.selectbox("Режисер", spysok_rezhyseriv())
    min_tryvalist = st.slider("Мінімальна тривалість фільму, хвилин", 0, 240, 0, step=5)

    st.divider()
    st.header("Додати нагороду (awards)")
    filmy_spysok = spysok_filmiv()
    obranuy_film = st.selectbox(
        "Фільм",
        options=filmy_spysok,
        format_func=lambda x: f"{x[1]} ({x[2]}) [id={x[0]}]",
    )
    with st.form("dodaty"):
        festival = st.text_input("Кінофестиваль", value="Молодість")
        award_year = st.number_input("Рік нагороди", min_value=1920, max_value=2026, value=1965, step=1)
        won = st.selectbox("Статус", options=[1, 0], format_func=lambda v: "Перемога (1)" if v == 1 else "Номінація (0)")
        nadislano = st.form_submit_button("Додати")

    if nadislano:
        if not festival.strip():
            st.error("Вкажіть назву кінофестивалю.")
        else:
            with zyednannya() as conn:
                conn.execute(
                    "INSERT INTO awards (film_id, festival, year, won) VALUES (?, ?, ?, ?)",
                    (obranuy_film[0], festival.strip(), int(award_year), int(won)),
                )
            st.session_state["dodano_nagorod"] += 1
            st.session_state["ostannya_nagoroda"] = f"{obranuy_film[1]} — {festival.strip()} ({int(award_year)})"
            st.cache_data.clear()
            st.success("Запис додано до таблиці awards!")

    st.caption(f"Додано за сесію: **{st.session_state['dodano_nagorod']}**")
    st.caption(f"Останній запис: {st.session_state['ostannya_nagoroda']}")

df = chytaty_filmy(rik_vid, rik_do, data_vid, data_do, rezhyser, min_tryvalist)
df_misyatsi = chytaty_po_misyatsyakh(rik_vid, rik_do, data_vid, data_do, rezhyser, min_tryvalist)

unique_directors = int(df["rezhyser"].nunique()) if not df.empty else 0
c1, c2, c3 = st.columns(3)
c1.metric("Кількість різних режисерів у вибірці", unique_directors)
c2.metric("Фільмів у вибірці", len(df))
c3.metric("Усього нагород у вибірці", int(df["nagorod"].sum()) if not df.empty else 0)

if df.empty:
    st.info("За обраними фільтрами фільмів не знайдено. Змініть параметри у бічній панелі.")
else:
    tab_dani, tab_grafiky = st.tabs(["Дані", "Графіки"])

    with tab_dani:
        st.dataframe(df, width="stretch")

    with tab_grafiky:
        st.subheader("Топ-10 фільмів за кількістю глядачів")
        top10 = df.nlargest(10, "glyadachiv").sort_values("glyadachiv", ascending=True)
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.barh(top10["nazva"], top10["glyadachiv"], color="#2b6cb0")
        ax.set_xlabel("Сумарна кількість глядачів")
        ax.set_ylabel("Фільм")
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        st.subheader("Кількість переглядів за місяцями")
        if df_misyatsi.empty:
            st.info("Немає переглядів за обраний період.")
        else:
            st.line_chart(df_misyatsi.set_index("misyats")["pereglyadiv"])
