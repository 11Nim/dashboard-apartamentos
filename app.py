from pathlib import Path

import altair as alt
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
import streamlit as st

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(page_title="Apartamentos novos", layout="wide")

PASTA_DADOS = Path(__file__).parent / "ArquivosCSV"
FONTE = "Fonte: [ATENÇÃO: preencha com a fonte real dos seus CSVs, ex.: ITBI - Prefeitura de Porto Alegre]"


# ============================================================
# DADOS
# ============================================================
@st.cache_data
def carregar_dados():
    arquivos = sorted(PASTA_DADOS.glob("*.csv"))
    if not arquivos:
        st.error(f"Nenhum CSV encontrado em {PASTA_DADOS}")
        st.stop()

    dfs = []
    for arq in arquivos:
        df = pd.read_csv(arq, sep=";", quotechar="'", encoding="utf-8")
        df["ano"] = int(arq.stem)  # ano numérico
        dfs.append(df)
    dados = pd.concat(dfs, ignore_index=True)

    # Recorte: apartamentos com área válida
    aptos = dados[
        (dados["finalidade_construcao"] == "APARTAMENTO")
        & (dados["area_constr_privativa"] > 0)
        & (dados["base_de_calculo"] > 0)
    ].copy()

    aptos["preco_m2"] = (aptos["base_de_calculo"] / aptos["area_constr_privativa"]).round(2)

    # Remove valores absurdos (erros de digitação) usando percentis
    p1, p99 = aptos["preco_m2"].quantile([0.01, 0.99])
    aptos = aptos[aptos["preco_m2"].between(p1, p99)]
    return aptos


aptos = carregar_dados()

# ============================================================
# CABEÇALHO
# ============================================================
st.title("🏢 Mercado de apartamentos novos")
st.markdown(
    "Painel para **compradores e investidores** que querem entender preços e "
    "volume de vendas de apartamentos em prédios recentes, por bairro."
)
st.caption(FONTE)

# ============================================================
# CONTROLES (barra lateral)
# ============================================================
st.sidebar.header("Filtros")

todos_bairros = sorted(aptos["bairro"].dropna().unique())
padrao = [b for b in ["AUXILIADORA", "MOINHOS VENTO", "PARTENON", "HIGIENOPOLIS", "RESTINGA"]
          if b in todos_bairros]

bairros_sel = st.sidebar.multiselect("Bairros", todos_bairros, default=padrao)

anos = sorted(aptos["ano"].unique())
ano_ini, ano_fim = st.sidebar.select_slider(
    "Período (ano da venda)", options=anos, value=(anos[0], anos[-1])
)

c_min, c_max = int(aptos["ano_construcao"].min()), int(aptos["ano_construcao"].max())
ano_constr = st.sidebar.slider(
    "Ano de construção do prédio (mínimo)", c_min, c_max, max(c_min, 2007)
)

# ============================================================
# APLICAÇÃO DOS FILTROS
# ============================================================
filtrado = aptos[
    aptos["bairro"].isin(bairros_sel)
    & aptos["ano"].between(ano_ini, ano_fim)
    & (aptos["ano_construcao"] >= ano_constr)
]

if filtrado.empty:
    st.warning("Nenhum registro para a combinação de filtros escolhida. "
               "Tente ampliar o período, incluir mais bairros ou reduzir o ano de construção.")
    st.stop()

# Indicadores rápidos
col1, col2, col3 = st.columns(3)
col1.metric("Vendas no recorte", f"{len(filtrado):,}".replace(",", "."))
col2.metric("Preço médio do m²", f"R$ {filtrado['preco_m2'].mean():,.0f}".replace(",", "."))
col3.metric("Bairros selecionados", filtrado["bairro"].nunique())

# ============================================================
# PERGUNTA 1: EVOLUÇÃO DO PREÇO
# ============================================================
st.header("1. Como evoluiu o preço do m²?")

media = filtrado.groupby(["ano", "bairro"], as_index=False)["preco_m2"].mean()
fig1 = px.line(
    media, x="ano", y="preco_m2", color="bairro", markers=True,
    labels={"ano": "Ano da venda", "preco_m2": "Preço médio por m² (R$)", "bairro": "Bairro"},
    title="Preço médio por m² ao longo dos anos",
)
fig1.update_xaxes(dtick=1)
st.plotly_chart(fig1, use_container_width=True)
st.caption("Cada ponto é a média das vendas do bairro no ano. Bairros com poucas vendas "
           "podem oscilar bastante de um ano para outro.")

# ============================================================
# PERGUNTA 2: VOLUME E DISPERSÃO
# ============================================================
st.header("2. Onde há mais vendas e quão variados são os preços?")

esq, dir_ = st.columns(2)

with esq:
    contagem = filtrado.groupby(["ano", "bairro"]).size().reset_index(name="quantidade")
    graf2 = (
        alt.Chart(contagem, title="Quantidade de vendas por ano e bairro")
        .mark_bar()
        .encode(
            x=alt.X("ano:O", title="Ano da venda"),
            y=alt.Y("quantidade:Q", title="Nº de vendas"),
            color=alt.Color("bairro:N", title="Bairro"),
            xOffset="bairro:N",
            tooltip=["ano", "bairro", "quantidade"],
        )
    )
    st.altair_chart(graf2, use_container_width=True)

with dir_:
    fig3, ax = plt.subplots(figsize=(7, 5))
    sns.boxplot(data=filtrado, x="bairro", y="preco_m2", ax=ax)
    ax.set_title("Distribuição do preço por m² por bairro")
    ax.set_xlabel("Bairro")
    ax.set_ylabel("Preço por m² (R$)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    st.pyplot(fig3)

st.caption("Esquerda: volume de vendas registradas. Direita: a caixa mostra onde estão "
           "50% das vendas; a linha central é a mediana; os pontos são casos atípicos.")

# ============================================================
# RODAPÉ
# ============================================================
st.divider()
st.caption(FONTE + " | Preço/m² = base de cálculo ÷ área privativa construída. "
           "Valores abaixo do percentil 1% e acima do 99% foram removidos.")