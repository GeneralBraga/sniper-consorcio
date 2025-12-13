
import streamlit as st
import pandas as pd
import re
import io
import xlsxwriter
import os

# --- CONFIGURAÇÃO VISUAL (DARK/GOLD - IGUAL AO SEU PRINT) ---
st.set_page_config(page_title="JBS SNIPER V38", layout="wide", page_icon="🎯")

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
    st.markdown(f"<h1 style='margin-top: 15px; margin-bottom: 0px;'>SISTEMA SNIPER V38</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin-top: 0px; color: {COLOR_BEIGE} !important;'>Ferramenta Exclusiva - Modo Deep Scan</h3>", unsafe_allow_html=True)
st.markdown(f"<hr style='border: 1px solid {COLOR_GOLD}; margin-top: 0;'>", unsafe_allow_html=True)

# --- FUNÇÕES INTELIGENTES ---
def limpar_moeda(texto):
    if not texto: return 0.0
    # Remove tudo que não for dígito ou vírgula decimal
    texto_clean = str(texto).lower().replace('r$', '').replace(' ', '').replace('.', '')
    # Se tiver vírgula, substitui por ponto
    texto_clean = texto_clean.replace(',', '.')
    try: return float(re.findall(r"[\d\.]+", texto_clean)[0])
    except: return 0.0

def classificar_status(custo_real):
    if custo_real <= 0.18: return "💎 LUCRO COM DESÁGIO"
    if custo_real <= 0.25: return "🔥 IMPERDÍVEL"
    if custo_real <= 0.35: return "✅ OPORTUNIDADE"
    return "⚠️ PADRÃO"

def extrair_piffer_v38(texto_bruto):
    lista_cotas = []
    
    # Normaliza espaços
    texto_limpo = re.sub(r'\s+', ' ', texto_bruto)
    # Tenta separar por linhas lógicas. Se for tudo uma tripa, separar por padrões de Admin
    if "\n" not in texto_bruto and len(texto_bruto) > 200:
        # Tenta inserir quebras antes de nomes de bancos comuns
        padrao_bancos = r'(?i)(Bradesco|Santander|Itaú|Itau|Porto|Caixa|Banco do Brasil|BB|Rodobens|Embracon|Âncora|Ancora|Mycon|Sicredi|Sicoob|Mapfre|Yamaha|Zema|Bancorbrás|Servopa|Unifisa)'
        texto_bruto = re.sub(padrao_bancos, r'\n\1', texto_bruto)

    linhas = [line.strip() for line in texto_bruto.splitlines() if line.strip()]
    
    admins_list = ['BRADESCO', 'SANTANDER', 'ITAÚ', 'ITAU', 'PORTO', 'CAIXA', 'BANCO DO BRASIL', 'BB', 'RODOBENS', 'EMBRACON', 'ANCORA', 'ÂNCORA', 'MYCON', 'SICREDI', 'SICOOB', 'MAPFRE', 'HS', 'YAMAHA', 'ZEMA', 'BANCORBRÁS', 'SERVOPA', 'UNIFISA', 'REPASSE']

    for linha in linhas:
        linha_lower = linha.lower()
        
        # 1. Identificar Admin (Obrigatório para ser uma linha válida)
        admin_encontrada = "OUTROS"
        tem_admin = False
        for adm in admins_list:
            if adm.lower() in linha_lower:
                admin_encontrada = adm.upper()
                tem_admin = True
                break
        
        # Se não achou admin, mas tem valores altos, pode ser cota. Se não, pula.
        # Mas para garantir "achar todas", vamos ser flexíveis se tiver formato de dinheiro.
        has_money_format = re.search(r'\d{1,3}(?:\.\d{3})*,\d{2}', linha)
        if not tem_admin and not has_money_format:
            continue

        # 2. Identificar Tipo
        tipo_bem = "Outros"
        if "imóvel" in linha_lower or "imovel" in linha_lower: tipo_bem = "Imóvel"
        elif "automóvel" in linha_lower or "veículo" in linha_lower or "carro" in linha_lower: tipo_bem = "Automóvel"
        elif "caminhão" in linha_lower or "pesado" in linha_lower: tipo_bem = "Pesados"

        # 3. EXTRAÇÃO DE VALORES (Agora pega números tipo 100.000,00 mesmo sem R$)
        # Regex procura: digitos, ponto, digitos, virgula, 2 digitos
        valores_raw = re.findall(r'(?:R\$)?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', linha)
        valores_float = sorted([limpar_moeda(v) for v in valores_raw], reverse=True)
        
        if len(valores_float) < 2: continue # Precisa pelo menos Credito e Entrada
        credito = valores_float[0]
        
        # 4. IDENTIFICAÇÃO DE PRAZO E PARCELA (DEEP SCAN)
        
        # Estratégia A: Procura explícito "Nx" ou "N parcelas"
        padrao_x = re.findall(r'(\d+)\s*[xX]\s*(?:R\$)?\s?([\d\.,]+)', linha_lower)
        
        prazo_final = 0
        parcela_final = 0.0
        saldo_devedor_real = 0.0
        
        if padrao_x:
            # Lógica de Soma (Junção)
            for pz_str, vlr_str in padrao_x:
                p = int(pz_str)
                v = limpar_moeda(vlr_str)
                saldo_devedor_real += (p * v)
                if p > prazo_final: # O prazo principal é o maior encontrado
                    prazo_final = p
                    parcela_final = v
        else:
            # Estratégia B: PRAZO NUMERAL SOLTO
            # Procura inteiros isolados entre 12 e 360 (excluindo os valores monetários já achados)
            # Regex para inteiros
            inteiros = re.findall(r'(?<![\d,])(\d{2,3})(?![\d,])', linha) # Números de 2 ou 3 digitos
            candidatos_prazo = [int(x) for x in inteiros if 12 <= int(x) <= 360]
            
            if candidatos_prazo:
                prazo_final = max(candidatos_prazo) # Assume o maior inteiro como prazo
                
                # Tenta achar a parcela (um valor menor que a entrada e crédito)
                # Geralmente a parcela é o menor valor monetário encontrado na linha
                candidatos_parcela = [v for v in valores_float if v < (credito * 0.1)] # Parcela < 10% do crédito
                if candidatos_parcela:
                    parcela_final = candidatos_parcela[-1] # O menor valor
                    saldo_devedor_real = prazo_final * parcela_final
            
        # 5. DEFINIR ENTRADA
        # A entrada geralmente é o segundo maior valor, mas não pode ser o saldo devedor
        candidatos_entrada = [x for x in valores_float if x != credito and abs(x - saldo_devedor_real) > 10 and abs(x - parcela_final) > 1]
        
        if candidatos_entrada:
            entrada = candidates_entrada = candidatos_entrada[0]
        else:
            entrada = 0.0
            # Fallback: Se não achou entrada, tenta deduzir: Valor 2 é entrada?
            if len(valores_float) >= 2: entrada = valores_float[1]

        # Cálculos Finais
        if saldo_devedor_real == 0 and prazo_final > 0 and parcela_final > 0:
            saldo_devedor_real = prazo_final * parcela_final
            
        custo_total = saldo_devedor_real + entrada
        
        custo_real_pct = ((custo_total / credito) - 1) if credito > 0 else 0
        entrada_pct = (entrada / credito) if credito > 0 else 0
        status = classificar_status(custo_real_pct)
        detalhes = linha[:120]

        # Só adiciona se tiver dados minimamente coerentes
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
                'Detalhes': detalhes
            })

    return pd.DataFrame(lista_cotas)

# --- INTERFACE ---
with st.expander("📋 DADOS DO SITE (Colar aqui)", expanded=True):
    texto_site = st.text_area("", height=100, key="input_texto", placeholder="Cole os dados (ex: Bradesco 100.000,00 30.000,00 180 800,00)...")

if 'df_resultado' not in st.session_state: st.session_state.df_resultado = None

# PROCESSAMENTO
if texto_site:
    df_raw = extrair_piffer_v38(texto_site)
    st.session_state.df_resultado = df_raw
    if not df_raw.empty:
        st.info(f"Deep Scan: {len(df_raw)} oportunidades identificadas.")
    else:
        st.warning("Nenhum dado identificado. Tente copiar e colar novamente.")

# --- FILTROS VISUAIS ---
st.subheader("Filtros JBS")

if st.session_state.df_resultado is not None and not st.session_state.df_resultado.empty:
    df = st.session_state.df_resultado.copy()
    
    # Filtros
    c1, c2 = st.columns(2)
    with c1:
        tipos = ["Todos"] + list(df['Tipo'].unique())
        f_tipo = st.selectbox("Tipo de Bem", tipos)
    with c2:
        admins = ["Todas"] + list(df['Admin'].unique())
        f_admin = st.selectbox("Administradora", admins)

    c3, c4 = st.columns(2)
    min_c = c3.number_input("Crédito Mín (R$)", value=0.0, step=1000.0)
    max_c = c3.number_input("Crédito Máx (R$)", value=10000000.0, step=1000.0)
    max_e = c4.number_input("Entrada Máx (R$)", value=10000000.0, step=1000.0)
    max_p = c4.number_input("Parcela Máx (R$)", value=100000.0, step=100.0)
    max_k = st.slider("Custo Máx (%)", 0.0, 1.0, 0.60, 0.01)

    # Aplicação
    if f_tipo != "Todos": df = df[df['Tipo'] == f_tipo]
    if f_admin != "Todas": df = df[df['Admin'] == f_admin]
    df = df[(df['Crédito'] >= min_c) & (df['Crédito'] <= max_c) & (df['Entrada'] <= max_e) & (df['Parcela'] <= max_p) & (df['% Custo'] <= max_k)]
    
    df = df.sort_values(by='% Custo', ascending=True)

    if st.button("🔍 LOCALIZAR OPORTUNIDADES"):
        st.success(f"✅ {len(df)} Cotas Encontradas!")
        
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

        # DOWNLOAD
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='JBS_SNIPER')
            wb = writer.book
            ws = writer.sheets['JBS_SNIPER']
            fmt_head = wb.add_format({'bold': True, 'fg_color': '#1f4e3d', 'font_color': 'white', 'border': 1})
            fmt_money = wb.add_format({'num_format': 'R$ #,##0.00'})
            fmt_pct = wb.add_format({'num_format': '0.00%'})
            
            for idx, val in enumerate(df.columns): ws.write(0, idx, val, fmt_head)
            ws.set_column('A:B', 20)
            ws.set_column('C:E', 18, fmt_money)
            ws.set_column('F:F', 12, fmt_pct)
            ws.set_column('G:I', 18, fmt_money)
            ws.set_column('J:J', 18, fmt_money)
            ws.set_column('K:K', 12, fmt_pct)
            
        st.download_button("📥 BAIXAR EXCEL", buf.getvalue(), "JBS_Sniper_V38.xlsx")
