
import streamlit as st
import pandas as pd
import re
import io
import xlsxwriter
import os

# --- CONFIGURAÇÃO DA PÁGINA (DARK/GOLD JBS) ---
st.set_page_config(page_title="JBS SNIPER V43", layout="wide", page_icon="🎯")

COLOR_GOLD = "#84754e"
COLOR_BEIGE = "#ecece4"
COLOR_BG = "#0e1117"
COLOR_INPUT_BG = "#1c1f26"

st.markdown(f"""
<style>
    .stApp {{background-color: {COLOR_BG}; color: {COLOR_BEIGE};}}
    .stButton>button {{width: 100%; background-color: {COLOR_GOLD}; color: white; border: none; border-radius: 6px; font-weight: bold; text-transform: uppercase; padding: 12px;}}
    .stButton>button:hover {{background-color: #6b5e3d;}}
    h1, h2, h3 {{color: {COLOR_GOLD} !important; font-family: 'Helvetica', sans-serif;}}
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div {{background-color: {COLOR_INPUT_BG}; color: white; border: 1px solid {COLOR_GOLD};}}
    div[data-baseweb="select"] > div {{background-color: {COLOR_INPUT_BG}; color: white; border: 1px solid {COLOR_GOLD};}}
    .stTextArea textarea {{background-color: {COLOR_INPUT_BG} !important; color: #ffffff !important; border: 1px solid {COLOR_GOLD} !important;}}
    div[data-testid="stDataFrame"], .streamlit-expanderHeader {{border: 1px solid {COLOR_GOLD}; background-color: {COLOR_INPUT_BG};}}
    .streamlit-expanderHeader {{ color: {COLOR_GOLD} !important; font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

# --- CABEÇALHO ---
c1, c2 = st.columns([1, 5])
with c1:
    if os.path.exists("logo_app.png"): st.image("logo_app.png", width=220)
    else: st.markdown(f"<h1 style='color:{COLOR_GOLD}'>JBS</h1>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<h1 style='margin-top: 15px; margin-bottom: 0px;'>SISTEMA SNIPER V43</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin-top: 0px; color: {COLOR_BEIGE} !important;'>JBS Contempladas - Edição Trator (Sem Erros)</h3>", unsafe_allow_html=True)
st.markdown(f"<hr style='border: 1px solid {COLOR_GOLD}; margin-top: 0;'>", unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_moeda(texto):
    if not texto: return 0.0
    try:
        texto_clean = str(texto).replace('\xa0', '').strip().lower()
        texto_clean = texto_clean.replace('r$', '').replace(' ', '').replace('.', '')
        texto_clean = texto_clean.replace(',', '.')
        match = re.search(r"[\d\.]+", texto_clean)
        return float(match.group(0)) if match else 0.0
    except:
        return 0.0

def classificar_status(custo_real):
    if custo_real <= 0.18: return "💎 LUCRO COM DESÁGIO"
    if custo_real <= 0.25: return "🔥 IMPERDÍVEL"
    if custo_real <= 0.35: return "✅ OPORTUNIDADE"
    return "⚠️ PADRÃO"

def extrair_piffer_v43(texto_bruto, modo_tipo):
    lista_cotas = []
    
    # LISTA EXATA DO SEU PRINT (ORDEM DO MAIOR PARA O MENOR É IMPORTANTE PARA O REPLACE)
    # Isso evita o erro do Python com regex complexo. Vamos usar substituição direta.
    admins_list = [
        'CAIXA ECONÔMICA FEDERAL', 'PORTO SEGURO - UNICRED', 'PORTO SEGURO VP', 'REPASSE (CAPITAL DE GIRO)',
        'CONSÓRCIO ARAUCÁRIA', 'UNIÃO CATARINENSE', 'UNIÃO LONDRINA', 'UNICOOB/SICOOB', 'SICOOB UNICOOB',
        'BANCO DO BRASIL', 'SICOOB PONTA', 'PORTO SEGURO', 'BSB DISBRAVE', 'GM - CHEVROLET', 'PRIMO ROSSI',
        'BANCORBRÁS', 'TRADIÇÃO', 'BRADESCO', 'EMBRACON', 'RODOBENS', 'SANTANDER', 'SERVOPA', 'UNIFISA',
        'BREITKOPF', 'ARAUCÁRIA', 'BANRISUL', 'CANOPUS', 'ADEMICON', 'BRQUALY', 'AGIBANK', 'SICREDI',
        'YAMAHA', 'MAPFRE', 'MAGALU', 'VOLVO', 'HONDA', 'GLOBO', 'GAZIN', 'SCANIA', 'REMAZA', 'RANDON',
        'VOLKSWAGEN', 'ITAÚ - A', 'ITAU - A', 'ITAÚ - M', 'ITAU - M', 'ITAÚ - P', 'ITAU - P', 
        'ITAÚ', 'ITAU', 'ÂNCORA', 'ANCORA', 'ALPHA VP', 'ALPHA', 'MYCON', 'MAGGI', 'IVECO', 
        'GROSCON', 'FORD', 'CAOA', 'ZEMA', 'RECON', 'HS', 'BB', 'CAIXA'
    ]
    
    # 1. TRATAMENTO DE TEXTO (A CORREÇÃO DO ERRO)
    # Em vez de um regex gigante que quebra o Python, vamos iterar a lista.
    texto_tratado = texto_bruto
    
    # Normaliza quebras de linha para evitar blocos gigantes
    if "\n" not in texto_tratado:
        # Insere quebra antes de R$ se estiver muito grudado
        texto_tratado = texto_tratado.replace("R$", " R$")

    for adm in admins_list:
        # Usa re.escape para garantir que parenteses não quebrem o código
        # Substitui "ADMINR$" por "ADMIN R$" (Case Insensitive via flag no sub, não no pattern)
        pattern = re.compile(re.escape(adm), re.IGNORECASE)
        
        # O segredo: Inserir quebra de linha antes do nome do banco para forçar estrutura de lista
        # E garantir espaço depois.
        texto_tratado = pattern.sub(lambda m: "\n" + m.group(0).upper() + " ", texto_tratado)

    # Divide em linhas agora que garantimos as quebras
    linhas = [line.strip() for line in texto_tratado.splitlines() if line.strip()]

    for linha in linhas:
        linha_lower = linha.lower()
        
        # Ignora lixo
        if "melhor parcela" in linha_lower or "fale conosco" in linha_lower or "copyright" in linha_lower:
            continue

        # 2. IDENTIFICAR ADMIN NA LINHA
        admin_encontrada = "OUTROS"
        tem_admin = False
        for adm in admins_list:
            if adm.lower() in linha_lower:
                admin_encontrada = adm.upper()
                tem_admin = True
                break
        
        # Validação: Tem que ter dinheiro ou ser linha de admin identificada
        has_money = re.search(r'\d{1,3}(?:\.\d{3})*,\d{2}', linha)
        if not tem_admin and not has_money:
            continue

        # 3. EXTRAÇÃO DE VALORES
        # Pega todos os valores monetários da linha
        valores_raw = re.findall(r'(?:R\$)?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', linha, re.IGNORECASE)
        valores_float = sorted([limpar_moeda(v) for v in valores_raw], reverse=True)
        
        if len(valores_float) < 2: continue # Precisa de Crédito e Entrada
        credito = valores_float[0]
        
        # 4. CÁLCULO DA SOMA DE PARCELAS (JUNÇÃO)
        # Procura "180x Valor"
        padrao_x = re.findall(r'(\d+)\s*[xX]\s*(?:R\$)?\s?([\d\.,]+)', linha_lower)
        
        prazo_final = 0
        parcela_final = 0.0
        saldo_devedor_real = 0.0
        
        if padrao_x:
            for pz_str, vlr_str in padrao_x:
                p = int(pz_str)
                v = limpar_moeda(vlr_str)
                saldo_devedor_real += (p * v) # SOMA TUDO
                if p > prazo_final:
                    prazo_final = p
                    parcela_final = v
        else:
            # Fallback para numerais soltos (ex: "180" e valor menor)
            inteiros = re.findall(r'(?<![\d,])(\d{2,3})(?![\d,])', linha)
            candidatos_prazo = [int(x) for x in inteiros if 12 <= int(x) <= 360]
            if candidatos_prazo:
                prazo_final = max(candidatos_prazo)
                candidatos_parcela = [v for v in valores_float if v < (credito * 0.1) and v > 10]
                if candidatos_parcela:
                    parcela_final = candidatos_parcela[-1]
                    saldo_devedor_real = prazo_final * parcela_final

        # 5. ENTRADA (Segundo maior valor, diferente do saldo)
        candidatos_entrada = [x for x in valores_float if x != credito and abs(x - saldo_devedor_real) > 10]
        entrada = candidates_entrada[0] if candidatos_entrada else (valores_float[1] if len(valores_float) > 1 else 0.0)

        # Finaliza
        if saldo_devedor_real == 0 and prazo_final > 0 and parcela_final > 0:
            saldo_devedor_real = prazo_final * parcela_final
            
        custo_total = saldo_devedor_real + entrada
        custo_real_pct = ((custo_total / credito) - 1) if credito > 0 else 0
        entrada_pct = (entrada / credito) if credito > 0 else 0
        status = classificar_status(custo_real_pct)
        
        # 6. TIPO (SEM DEDUÇÃO BURRA - USA O SELETOR)
        tipo_bem = "A Classificar"
        # Prioridade 1: Escrito na linha
        if "imóvel" in linha_lower or "imovel" in linha_lower: tipo_bem = "Imóvel"
        elif "automóvel" in linha_lower or "auto" in linha_lower or "veículo" in linha_lower: tipo_bem = "Automóvel"
        elif "caminhão" in linha_lower or "pesado" in linha_lower: tipo_bem = "Pesados"
        # Regras fixas de admin
        elif "itaú - a" in linha_lower or "volkswagen" in linha_lower: tipo_bem = "Automóvel"
        elif "itaú - i" in linha_lower: tipo_bem = "Imóvel"
        
        # Prioridade 2: Seletor Manual (O que o usuário mandou)
        if tipo_bem == "A Classificar":
            if modo_tipo == "Lote de Imóveis": tipo_bem = "Imóvel"
            elif modo_tipo == "Lote de Autos": tipo_bem = "Automóvel"
            elif modo_tipo == "Lote de Pesados": tipo_bem = "Pesados"

        if credito > 1000: 
            lista_cotas.append({
                'Status': status,
                'Admin': admin_encontrada,
                'Tipo': tipo_bem,
                'Crédito': credito,
                'Entrada': entrada,
                '% Entrada': entrada_pct,
                'Prazo': int(prazo_final),
                'Parcela': parcela_final,
                'Saldo Devedor': saldo_devedor_real,
                'Custo Total': custo_total,
                '% Custo': custo_real_pct,
                'Detalhes': linha[:150]
            })

    return pd.DataFrame(lista_cotas)

# --- INTERFACE ---
with st.expander("📋 COLE OS DADOS AQUI (CTRL+V)", expanded=True):
    st.info("💡 IMPORTANTE: Selecione abaixo o tipo de lote que você copiou para garantir a classificação correta.")
    modo_leitura = st.radio(
        "O que você está colando?",
        ["🕵️ Detectar (Texto)", "🏠 Lote de Imóveis", "🚗 Lote de Autos", "🚛 Lote de Pesados"],
        horizontal=True,
        index=0
    )
    
    texto_site = st.text_area("", height=200, key="input_texto", placeholder="Cole aqui os dados copiados do site Piffer...")

if 'df_resultado' not in st.session_state: st.session_state.df_resultado = None

if texto_site:
    try:
        df_raw = extrair_piffer_v43(texto_site, modo_leitura)
        st.session_state.df_resultado = df_raw
        if not df_raw.empty:
            st.success(f"✅ {len(df_raw)} cotas processadas e separadas!")
        else:
            st.warning("⚠️ Nenhuma cota encontrada. O texto copiado contém valores 'R$'?")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")

# --- FILTROS JBS ---
st.subheader("Filtros JBS")

if st.session_state.df_resultado is not None and not st.session_state.df_resultado.empty:
    df = st.session_state.df_resultado.copy()
    
    c1, c2 = st.columns(2)
    with c1:
        tipos_disp = ["Todos"] + sorted(list(df['Tipo'].unique()))
        f_tipo = st.selectbox("Tipo de Bem", tipos_disp)
    with c2:
        admins_disp = ["Todas"] + sorted(list(df['Admin'].unique()))
        f_admin = st.selectbox("Administradora", admins_disp)

    c3, c4 = st.columns(2)
    min_c = c3.number_input("Crédito Mín (R$)", value=0.0, step=5000.0)
    max_c = c3.number_input("Crédito Máx (R$)", value=10000000.0, step=5000.0)
    max_e = c4.number_input("Entrada Máx (R$)", value=10000000.0, step=5000.0)
    max_p = c4.number_input("Parcela Máx (R$)", value=100000.0, step=100.0)
    max_k = st.slider("Custo Máx (%)", 0.0, 1.0, 0.65, 0.01)

    if f_tipo != "Todos": df = df[df['Tipo'] == f_tipo]
    if f_admin != "Todas": df = df[df['Admin'] == f_admin]
    df = df[
        (df['Crédito'] >= min_c) & 
        (df['Crédito'] <= max_c) & 
        (df['Entrada'] <= max_e) & 
        (df['Parcela'] <= max_p) & 
        (df['% Custo'] <= max_k)
    ]
    
    df = df.sort_values(by='% Custo', ascending=True)

    if st.button("🔍 LOCALIZAR OPORTUNIDADES"):
        if not df.empty:
            st.success(f"✅ {len(df)} Oportunidades Filtradas!")
            
            st.dataframe(
                df,
                column_config={
                    "Crédito": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Entrada": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Parcela": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Saldo Devedor": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Custo Total": st.column_config.NumberColumn(format="R$ %.2f"),
                    "% Entrada": st.column_config.NumberColumn(format="%.2f %%"),
                    "% Custo": st.column_config.NumberColumn(format="%.2f %%"),
                }, hide_index=True, use_container_width=True
            )

            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='JBS_SNIPER')
                wb = writer.book
                ws = writer.sheets['JBS_SNIPER']
                
                fmt_head = wb.add_format({'bold': True, 'fg_color': '#1f4e3d', 'font_color': 'white', 'border': 1})
                fmt_money = wb.add_format({'num_format': 'R$ #,##0.00'})
                fmt_pct = wb.add_format({'num_format': '0.00%'})
                
                for idx, val in enumerate(df.columns): ws.write(0, idx, val, fmt_head)
                
                ws.set_column('A:A', 25)
                ws.set_column('B:C', 18)
                ws.set_column('D:E', 18, fmt_money)
                ws.set_column('F:F', 12, fmt_pct)
                ws.set_column('G:G', 10)
                ws.set_column('H:J', 18, fmt_money)
                ws.set_column('K:K', 12, fmt_pct)
                ws.set_column('L:L', 60)
                
            st.download_button("📥 BAIXAR EXCEL", buf.getvalue(), "JBS_Sniper_V43.xlsx")
        else:
            st.warning("Nenhuma cota sobrou após os filtros.")
