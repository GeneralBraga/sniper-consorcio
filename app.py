
import streamlit as st
import pandas as pd
import re
import itertools
from io import BytesIO
from fpdf import FPDF
from datetime import datetime
import os

# --- CONFIGURAÇÃO ---
favicon_path = "logo_pdf.png" if os.path.exists("logo_pdf.png") else "🏛️"
st.set_page_config(page_title="JBS SNIPER", page_icon=favicon_path, layout="wide")

# --- CORES ---
COLOR_GOLD = "#84754e"
COLOR_BEIGE = "#ecece4"
COLOR_BG = "#0e1117"

# --- CSS ---
st.markdown(f"""
<style>
    .stApp {{background-color: {COLOR_BG}; color: {COLOR_BEIGE};}}
    .stButton>button {{width: 100%; background-color: {COLOR_GOLD}; color: white; border: none; border-radius: 6px; font-weight: bold; text-transform: uppercase; padding: 12px;}}
    .stButton>button:hover {{background-color: #6b5e3d; color: {COLOR_BEIGE}; box-shadow: 0 2px 5px rgba(0,0,0,0.2);}}
    h1, h2, h3 {{color: {COLOR_GOLD} !important; font-family: 'Helvetica', sans-serif;}}
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div {{background-color: #1c1f26; color: white; border: 1px solid {COLOR_GOLD};}}
    div[data-testid="stDataFrame"], .streamlit-expanderHeader {{border: 1px solid {COLOR_GOLD}; background-color: #1c1f26;}}
</style>
""", unsafe_allow_html=True)

# --- CABEÇALHO ---
c1, c2 = st.columns([1, 5])
with c1:
    if os.path.exists("logo_app.png"): st.image("logo_app.png", width=220)
    else: st.markdown(f"<h1 style='color:{COLOR_GOLD}'>JBS</h1>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<h1 style='margin-top: 15px; margin-bottom: 0px;'>SISTEMA SNIPER</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin-top: 0px; color: {COLOR_BEIGE} !important;'>Ferramenta Exclusiva da JBS Contempladas</h3>", unsafe_allow_html=True)
st.markdown(f"<hr style='border: 1px solid {COLOR_GOLD}; margin-top: 0;'>", unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_moeda(texto):
    if not texto: return 0.0
    texto = str(texto).lower().strip().replace('\xa0', '').replace('&nbsp;', '')
    texto = re.sub(r'[^\d\.,]', '', texto)
    if not texto: return 0.0
    try:
        if ',' in texto and '.' in texto: return float(texto.replace('.', '').replace(',', '.'))
        elif ',' in texto: return float(texto.replace(',', '.'))
        elif '.' in texto:
             if len(texto.split('.')[1]) == 2: return float(texto)
             return float(texto.replace('.', ''))
        return float(texto)
    except: return 0.0

# --- EXTRATOR ESPECIALIZADO: PIFFER ---
def extrair_piffer(texto_copiado, tipo_selecionado):
    lista_cotas = []
    texto_limpo = "\n".join([line.strip() for line in texto_copiado.split('\n') if line.strip()])
    
    # Piffer geralmente quebra por Administradora ou Blocos visuais
    # Regex agressiva para achar "100x" ou "100 x"
    regex_padrao_piffer = r'(?i)(bradesco|santander|itaú|itau|porto|caixa|banco do brasil|bb|rodobens|embracon|ancora|âncora|mycon|sicredi|sicoob|mapfre|hs|yamaha|zema|bancorbrás|bancorbras|servopa)'
    
    blocos = re.split(regex_padrao_piffer, texto_limpo)
    
    # Reconstrói blocos (Admin + Conteúdo)
    blocos_reais = []
    if len(blocos) > 2:
        for i in range(1, len(blocos), 2):
            if i+1 < len(blocos): blocos_reais.append(blocos[i] + " " + blocos[i+1])
    else:
        blocos_reais = re.split(r'\n\s*\n', texto_limpo) # Fallback para quebra de linha

    id_cota = 1
    for bloco in blocos_reais:
        if len(bloco) < 20: continue
        bloco_lower = bloco.lower()
        
        # Admin
        match_admin = re.search(regex_padrao_piffer, bloco_lower)
        admin = match_admin.group(0).upper() if match_admin else "OUTROS"
        if admin == "OUTROS" and "r$" not in bloco_lower: continue

        # Valores (Piffer: Maior=Crédito, Segundo=Entrada)
        valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
        vals_float = sorted([limpar_moeda(v) for v in valores], reverse=True)
        
        credito = vals_float[0] if len(vals_float) >= 1 else 0.0
        entrada = vals_float[1] if len(vals_float) >= 2 else 0.0
        
        # Parcela e Prazo (O Ponto Crítico da Piffer)
        # Procura padrões como "135 x R$ 519,82" ou "37 x R$ 953,00"
        # Regex específica para capturar (Prazo, Valor)
        padrao_parcela = re.findall(r'(\d{1,3})\s*[xX]\s*R?\$\s?([\d\.,]+)', bloco)
        
        parcela = 0.0
        prazo = 0
        saldo_devedor = 0.0
        
        if padrao_parcela:
            # Pega a parcela com maior valor monetário (evita pegar taxas pequenas)
            # Converte para float para comparar
            parcelas_validas = []
            for p, v in padrao_parcela:
                v_float = limpar_moeda(v)
                p_int = int(p)
                if v_float > 100: # Filtro de ruído
                    parcelas_validas.append((p_int, v_float))
            
            if parcelas_validas:
                # Ordena pelo valor da parcela (maior parcela costuma ser a principal)
                parcelas_validas.sort(key=lambda x: x[1], reverse=True)
                prazo = parcelas_validas[0][0]
                parcela = parcelas_validas[0][1]
                saldo_devedor = prazo * parcela

        if credito > 5000:
            # Se não achou saldo via parcelas, estima
            if saldo_devedor == 0 and entrada > 0: 
                saldo_devedor = (credito * 1.3) - entrada
                # Tenta inferir parcela e prazo reverso
                if prazo == 0: prazo = 100 # Chute conservador para não dividir por zero
                if parcela == 0: parcela = saldo_devedor / prazo

            custo_total = entrada + saldo_devedor
            lista_cotas.append({
                'ID': id_cota, 'Admin': admin, 'Tipo': tipo_selecionado,
                'Crédito': credito, 'Entrada': entrada,
                'Parcela': parcela, 'Saldo': saldo_devedor, 'CustoTotal': custo_total,
                'EntradaPct': (entrada/credito) if credito else 0
            })
            id_cota += 1
    return lista_cotas

# --- EXTRATOR: TOP CONTEMPLADAS (ROTULADO) ---
def extrair_top(texto_copiado, tipo_selecionado):
    lista_cotas = []
    texto_limpo = "\n".join([line.strip() for line in texto_copiado.split('\n') if line.strip()])
    # Quebra por linha dupla (padrão visual do Top)
    blocos = re.split(r'\n\s*\n', texto_limpo)
    
    id_cota = 1
    for bloco in blocos:
        if len(bloco) < 20: continue
        bloco_lower = bloco.lower()
        
        # Admin via Regex
        admins_regex = r'(?i)(bradesco|santander|itaú|itau|porto|caixa|banco do brasil|bb|rodobens|embracon|ancora|âncora|mycon|sicredi|sicoob|mapfre|hs|yamaha|zema)'
        match_admin = re.search(admins_regex, bloco_lower)
        admin = match_admin.group(0).upper() if match_admin else "OUTROS"
        if admin == "OUTROS" and "r$" not in bloco_lower: continue

        # Valores via Rótulo (Crédito: / Entrada:)
        credito = 0.0
        match_c = re.search(r'(?:crédito|bem|valor).*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_c: credito = limpar_moeda(match_c.group(1))
        
        entrada = 0.0
        match_e = re.search(r'(?:entrada|ágio).*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_e: entrada = limpar_moeda(match_e.group(1))
        
        # Fallback de posição se rótulo falhar
        if credito == 0:
            vals = sorted([limpar_moeda(v) for v in re.findall(r'R\$\s?([\d\.,]+)', bloco)], reverse=True)
            if vals: credito = vals[0]
            if entrada == 0 and len(vals)>1: entrada = vals[1]

        # Parcela (Top usa rótulo "Parcelas:")
        parcela = 0.0
        prazo = 0
        match_parc = re.search(r'(\d+)\s*[xX]\s*R?\$\s?([\d\.,]+)', bloco)
        if match_parc:
            prazo = int(match_parc.group(1))
            parcela = limpar_moeda(match_parc.group(2))
        
        saldo = prazo * parcela
        if saldo == 0 and credito > 0: saldo = (credito * 1.3) - entrada

        if credito > 5000:
            lista_cotas.append({
                'ID': id_cota, 'Admin': admin, 'Tipo': tipo_selecionado,
                'Crédito': credito, 'Entrada': entrada, 'Parcela': parcela,
                'Saldo': saldo, 'CustoTotal': entrada + saldo,
                'EntradaPct': (entrada/credito) if credito else 0
            })
            id_cota += 1
    return lista_cotas

def processar_combinacoes(cotas, min_cred, max_cred, max_ent, max_parc, max_custo, tipo_filtro, admin_filtro):
    combinacoes_validas = []
    cotas_por_admin = {}
    
    for cota in cotas:
        if admin_filtro != "Todas" and cota['Admin'] != admin_filtro: continue
        adm = cota['Admin']
        if adm not in cotas_por_admin: cotas_por_admin[adm] = []
        cotas_por_admin[adm].append(cota)
    
    progress_bar = st.progress(0)
    total_admins = len(cotas_por_admin)
    current = 0

    if total_admins == 0: return pd.DataFrame()

    for admin, grupo in cotas_por_admin.items():
        if admin == "OUTROS": continue
        current += 1
        progress_bar.progress(int((current / total_admins) * 100))
        grupo.sort(key=lambda x: x['EntradaPct'])
        
        count = 0
        max_ops = 5000000 
        
        for r in range(1, 7):
            iterator = itertools.combinations(grupo, r)
            while True:
                try:
                    combo = next(iterator)
                    count += 1
                    if count > max_ops: break
                    
                    soma_ent = sum(c['Entrada'] for c in combo)
                    if soma_ent > (max_ent * 1.05): continue
                    soma_cred = sum(c['Crédito'] for c in combo)
                    if soma_cred < min_cred or soma_cred > max_cred: continue
                    soma_parc = sum(c['Parcela'] for c in combo)
                    if soma_parc > (max_parc * 1.05): continue
                    
                    soma_saldo = sum(c['Saldo'] for c in combo)
                    custo_total_exibicao = soma_ent + soma_saldo
                    
                    # Cálculo Correto de Prazo Médio (Ponderado)
                    prazo_medio = 0
                    if soma_parc > 0: prazo_medio = int(soma_saldo / soma_parc)

                    custo_real = (custo_total_exibicao / soma_cred) - 1
                    if custo_real > max_custo: continue
                    
                    ids = " + ".join([str(c['ID']) for c in combo])
                    detalhes = " || ".join([f"[ID {c['ID']}] 💰 CR: R$ {c['Crédito']:,.0f}" for c in combo])
                    
                    status = "⚠️ PADRÃO"
                    if custo_real <= 0.20: status = "💎 OURO"
                    elif custo_real <= 0.35: status = "🔥 IMPERDÍVEL"
                    elif custo_real <= 0.45: status = "✨ EXCELENTE"
                    elif custo_real <= 0.50: status = "✅ OPORTUNIDADE"
                    
                    combinacoes_validas.append({
                        'STATUS': status,
                        'ADMINISTRADORA': admin,
                        'TIPO': c['Tipo'],
                        'IDS': ids,
                        'CRÉDITO TOTAL': soma_cred,
                        'ENTRADA TOTAL': soma_ent,
                        'ENTRADA %': (soma_ent / soma_cred) * 100,
                        'SALDO DEVEDOR': soma_saldo,
                        'CUSTO TOTAL': custo_total_exibicao,
                        'PRAZO': prazo_medio,
                        'PARCELAS': soma_parc,
                        'CUSTO EFETIVO %': custo_real * 100,
                        'DETALHES': detalhes
                    })
                    if len([x for x in combinacoes_validas if x['ADMINISTRADORA'] == admin]) > 500: break
                except StopIteration: break
            if count > max_ops: break
    progress_bar.empty()
    return pd.DataFrame(combinacoes_validas)

# --- PDF ---
class PDF(FPDF):
    def header(self):
        self.set_fill_color(132, 117, 78)
        self.rect(0, 0, 297, 22, 'F')
        if os.path.exists("logo_pdf.png"): self.image('logo_pdf.png', 5, 3, 35)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(255, 255, 255)
        self.set_xy(45, 6) 
        self.cell(0, 10, 'RELATÓRIO SNIPER DE OPORTUNIDADES', 0, 1, 'L')
        self.ln(8)

def limpar_emojis(texto):
    return texto.encode('latin-1', 'ignore').decode('latin-1').replace("?", "").strip()

def gerar_pdf_final(df):
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=7)
    pdf.set_fill_color(236, 236, 228)
    pdf.set_text_color(0)
    pdf.set_font("Arial", 'B', 7)
    headers = ["STS", "ADM", "TIPO", "CREDITO", "ENTRADA", "ENT%", "SALDO", "CUSTO TOT", "PRZ", "PARCELA", "EFET%", "DETALHES"]
    w = [20, 20, 12, 22, 22, 10, 22, 22, 8, 18, 10, 95] 
    for i, h in enumerate(headers): pdf.cell(w[i], 8, h, 1, 0, 'C', True)
    pdf.ln()
    pdf.set_font("Arial", size=7)
    for index, row in df.iterrows():
        status_clean = limpar_emojis(row['STATUS'])
        pdf.cell(w[0], 8, status_clean, 1, 0, 'C')
        pdf.cell(w[1], 8, limpar_emojis(str(row['ADMINISTRADORA'])), 1, 0, 'C')
        pdf.cell(w[2], 8, limpar_emojis(str(row['TIPO'])), 1, 0, 'C')
        pdf.cell(w[3], 8, f"{row['CRÉDITO TOTAL']:,.0f}", 1, 0, 'R')
        pdf.cell(w[4], 8, f"{row['ENTRADA TOTAL']:,.0f}", 1, 0, 'R')
        pdf.cell(w[5], 8, f"{row['ENTRADA %']:.1f}%", 1, 0, 'C')
        pdf.cell(w[6], 8, f"{row['SALDO DEVEDOR']:,.0f}", 1, 0, 'R')
        pdf.cell(w[7], 8, f"{row['CUSTO TOTAL']:,.0f}", 1, 0, 'R')
        pdf.cell(w[8], 8, str(row['PRAZO']), 1, 0, 'C')
        pdf.cell(w[9], 8, f"{row['PARCELAS']:,.0f}", 1, 0, 'R')
        pdf.cell(w[10], 8, f"{row['CUSTO EFETIVO %']:.1f}%", 1, 0, 'C')
        detalhe = limpar_emojis(row['DETALHES'])
        pdf.cell(w[11], 8, detalhe[:75], 1, 1, 'L')
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- APP ---
if 'df_resultado' not in st.session_state: st.session_state.df_resultado = None

with st.expander("📋 DADOS DO SITE (Colar aqui)", expanded=True):
    texto_site = st.text_area("", height=100, key="input_texto")

st.subheader("Filtros JBS")

# --- SELETOR DE ORIGEM DOS DADOS ---
origem_dados = st.selectbox("Qual site você copiou?", ["Site Piffer", "Top Contempladas / Outros"])
tipo_bem = st.selectbox("Tipo de Bem", ["Imóvel", "Automóvel", "Pesados", "Motos", "Todos"])

if texto_site and 'admins_disponiveis' not in st.session_state:
    st.session_state['admins_disponiveis'] = ["Todas"]

admin_filtro = st.selectbox("Administradora", st.session_state.get('admins_disponiveis', ["Todas"]))

c1, c2 = st.columns(2)
min_c = c1.number_input("Crédito Mín (R$)", 0.0, step=1000.0, value=60000.0, format="%.2f")
max_c = c1.number_input("Crédito Máx (R$)", 0.0, step=1000.0, value=710000.0, format="%.2f")
max_e = c2.number_input("Entrada Máx (R$)", 0.0, step=1000.0, value=200000.0, format="%.2f")
max_p = c2.number_input("Parcela Máx (R$)", 0.0, step=100.0, value=4500.0, format="%.2f")
max_k = st.slider("Custo Máx (%)", 0.0, 1.0, 0.55, 0.01)

if st.button("🔍 LOCALIZAR OPORTUNIDADES"):
    if texto_site:
        cotas = []
        # DECIDE QUAL MOTOR USAR
        if origem_dados == "Site Piffer":
            cotas = extrair_piffer(texto_site, tipo_bem)
        else:
            cotas = extrair_top(texto_site, tipo_bem) # Ou universal
            
        if cotas:
            # Atualiza lista de admins para filtro futuro
            admins = sorted(list(set([c['Admin'] for c in cotas])))
            st.session_state['admins_disponiveis'] = ["Todas"] + admins
            st.success(f"{len(cotas)} cotas lidas com sucesso!")
            
            st.session_state.df_resultado = processar_combinacoes(cotas, min_c, max_c, max_e, max_p, max_k, tipo_bem, admin_filtro)
        else:
            st.error("Nenhuma cota lida. Verifique o site selecionado.")
    else:
        st.error("Cole os dados.")

if st.session_state.df_resultado is not None:
    df_show = st.session_state.df_resultado
    if not df_show.empty:
        df_show = df_show.sort_values(by='CUSTO EFETIVO %')
        st.success(f"{len(df_show)} Oportunidades Encontradas!")
        
        st.dataframe(
            df_show,
            column_config={
                "CRÉDITO TOTAL": st.column_config.NumberColumn(format="R$ %.2f"),
                "ENTRADA TOTAL": st.column_config.NumberColumn(format="R$ %.2f"),
                "ENTRADA %": st.column_config.NumberColumn(format="%.2f %%"),
                "SALDO DEVEDOR": st.column_config.NumberColumn(format="R$ %.2f"),
                "CUSTO TOTAL": st.column_config.NumberColumn(format="R$ %.2f"),
                "PARCELAS": st.column_config.NumberColumn(format="R$ %.2f"),
                "CUSTO EFETIVO %": st.column_config.NumberColumn(format="%.2f %%"),
            }, hide_index=True
        )
        
        c_pdf, c_xls = st.columns(2)
        try:
            pdf_bytes = gerar_pdf_final(df_show)
            c_pdf.download_button("📄 Baixar PDF", pdf_bytes, "JBS_Relatorio.pdf", "application/pdf")
        except: c_pdf.error("Erro PDF")

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_ex = df_show.copy()
            df_ex['ENTRADA %'] = df_ex['ENTRADA %'] / 100
            df_ex['CUSTO EFETIVO %'] = df_ex['CUSTO EFETIVO %'] / 100
            df_ex.to_excel(writer, index=False, sheet_name='JBS')
            wb = writer.book
            ws = writer.sheets['JBS']
            header_fmt = wb.add_format({'bold': True, 'bg_color': '#ecece4', 'border': 1})
            fmt_money = wb.add_format({'num_format': 'R$ #,##0.00'})
            fmt_perc = wb.add_format({'num_format': '0.00%'})
            for col_num, value in enumerate(df_ex.columns.values): ws.write(0, col_num, value, header_fmt)
            ws.set_column('E:F', 18, fmt_money)
            ws.set_column('G:G', 12, fmt_perc)
            ws.set_column('H:I', 18, fmt_money)
            ws.set_column('K:K', 15, fmt_money)
            ws.set_column('L:L', 12, fmt_perc)
            ws.set_column('M:M', 70)
            ws.set_column('A:D', 15)
        c_xls.download_button("📊 Baixar Excel", buf.getvalue(), "JBS_Calculo.xlsx")
    else:
        st.warning("Nenhuma oportunidade com estes filtros.")
