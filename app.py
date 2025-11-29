
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
    .stButton>button {{width: 100%; background-color: {COLOR_GOLD}; color: white; border: none; border-radius: 6px; font-weight: bold; text-transform: uppercase; padding: 12px; letter-spacing: 1px;}}
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

def extrair_dados_universal(texto_copiado, tipo_selecionado):
    lista_cotas = []
    texto_limpo = "\n".join([line.strip() for line in texto_copiado.split('\n') if line.strip()])
    
    # Quebra de blocos por Administradora
    admins_regex = r'(?i)(bradesco|santander|itaú|itau|porto|caixa|banco do brasil|bb|rodobens|embracon|ancora|âncora|mycon|sicredi|sicoob|mapfre|hs|yamaha|zema|bancorbrás|bancorbras|servopa)'
    
    partes = re.split(f'({admins_regex})', texto_limpo)
    
    blocos_reais = []
    for i in range(1, len(partes), 2):
        if i+1 < len(partes):
            blocos_reais.append(partes[i] + " " + partes[i+1])
            
    if not blocos_reais:
        blocos_reais = re.split(r'\n\s*\n', texto_limpo)

    id_cota = 1
    for bloco in blocos_reais:
        if len(bloco) < 20: continue
        bloco_lower = bloco.lower()
        
        # 1. Admin
        match_admin = re.search(admins_regex, bloco_lower)
        admin_encontrada = match_admin.group(0).upper() if match_admin else "OUTROS"
        if admin_encontrada == "OUTROS" and "r$" not in bloco_lower: continue

        # 2. Tipo
        tipo_cota = "Geral"
        if "imóvel" in bloco_lower or "imovel" in bloco_lower: tipo_cota = "Imóvel"
        elif "automóvel" in bloco_lower or "veículo" in bloco_lower: tipo_cota = "Automóvel"
        
        if tipo_cota == "Geral": tipo_cota = tipo_selecionado

        # 3. Valores (Crédito e Entrada)
        credito = 0.0
        entrada = 0.0
        
        # Busca Primária (Rótulos)
        match_cred = re.search(r'(?:crédito|credito|bem|valor)[^\d\n]*?R\$\s?([\d\.,]+)', bloco_lower)
        match_ent = re.search(r'(?:entrada|ágio|agio|quero|pago)[^\d\n]*?R\$\s?([\d\.,]+)', bloco_lower)
        
        if match_cred: credito = limpar_moeda(match_cred.group(1))
        if match_ent: entrada = limpar_moeda(match_ent.group(1))
        
        # Busca Secundária (Posição)
        if credito == 0:
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            vals_float = sorted([limpar_moeda(v) for v in valores], reverse=True)
            if len(vals_float) >= 1: credito = vals_float[0]
            if len(vals_float) >= 2 and entrada == 0: 
                if vals_float[1] > (credito * 0.05): entrada = vals_float[1]

        # 4. PARCELAS E PRAZOS (MODO VARREDURA TOTAL)
        saldo_devedor = 0.0
        parcela_teto = 0.0
        prazo_final = 0
        
        # TENTATIVA 1: Regex Padrão (Nx R$ Y)
        todas_parcelas = re.findall(r'(\d{1,3})\s*(?:[xX]|vezes|parcelas.*?de)\s*R?\$\s?([\d\.,]+)', bloco)
        
        # TENTATIVA 2: Regex Invertida (R$ Y em Nx)
        if not todas_parcelas:
             todas_parcelas_inv = re.findall(r'R?\$\s?([\d\.,]+)\s*(?:em|x|durante)\s*(\d{1,3})', bloco)
             if todas_parcelas_inv: todas_parcelas = [(p[1], p[0]) for p in todas_parcelas_inv]

        # Processa o que achou
        if todas_parcelas:
            for pz_str, vlr_str in todas_parcelas:
                pz = int(pz_str)
                vlr = limpar_moeda(vlr_str)
                if pz > 360 or vlr < 50: continue 
                saldo_devedor += (pz * vlr)
                if vlr > parcela_teto: 
                    parcela_teto = vlr
                    prazo_final = pz
        else:
            # TENTATIVA 3 (DESESPERO): Procura valor pequeno isolado
            # Se não achou "X", procura só o R$ que seja pequeno
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            possiveis_parcelas = []
            for v in valores:
                vf = limpar_moeda(v)
                if credito > 0 and vf < (credito * 0.03) and vf > 100: # Parcela geralmente é < 3% do crédito
                    possiveis_parcelas.append(vf)
            
            if possiveis_parcelas:
                parcela_teto = max(possiveis_parcelas)
                # Estima saldo se tivermos parcela mas não prazo
                # Assume prazo médio de mercado se não tiver info
                prazo_est = 150 if tipo_cota == "Imóvel" else 70
                saldo_devedor = parcela_teto * prazo_est
                prazo_final = prazo_est

        # MONTAGEM FINAL (SEM DESCARTAR NADA VÁLIDO)
        if credito > 0 and entrada > 0:
            
            # Se ainda assim Saldo for 0 (site omitiu tudo), assume saldo matemático
            # Isso gera "Lucro 0%" mas permite ver a cota
            if saldo_devedor == 0:
                saldo_devedor = credito - entrada # Custo zero (apenas repasse)
            
            custo_total = entrada + saldo_devedor
            
            # Filtro mínimo de sanidade (só descarta se for erro de leitura brutal)
            if credito > 3000: 
                lista_cotas.append({
                    'ID': id_cota, 
                    'Admin': admin_encontrada, 
                    'Tipo': tipo_cota,
                    'Crédito': credito, 
                    'Entrada': entrada,
                    'Parcela': parcela_teto, 
                    'Saldo': saldo_devedor, 
                    'CustoTotal': custo_total,
                    'Prazo': prazo_final,
                    'EntradaPct': (entrada/credito) if credito else 0
                })
                id_cota += 1
    return lista_cotas

def processar_combinacoes(cotas, min_cred, max_cred, max_ent, max_parc, max_custo, tipo_filtro, admin_filtro):
    combinacoes_validas = []
    cotas_por_admin = {}
    
    for cota in cotas:
        if tipo_filtro != "Todos" and cota['Tipo'] != tipo_filtro: continue
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
                    
                    # Prazo Médio
                    prazo_medio = 0
                    if soma_parc > 0: prazo_medio = int(soma_saldo / soma_parc)

                    custo_real = (custo_total_exibicao / soma_cred) - 1
                    if custo_real > max_custo: continue
                    
                    ids = " + ".join([str(c['ID']) for c in combo])
                    detalhes = " || ".join([f"[ID {c['ID']}] 💰 CR: R$ {c['Crédito']:,.0f}" for c in combo])
                    tipo_final = combo[0]['Tipo']
                    
                    status = "⚠️ PADRÃO"
                    if custo_real <= 0.20: status = "💎 OURO"
                    elif custo_real <= 0.35: status = "🔥 IMPERDÍVEL"
                    elif custo_real <= 0.45: status = "✨ EXCELENTE"
                    elif custo_real <= 0.50: status = "✅ OPORTUNIDADE"
                    
                    entrada_pct = (soma_ent / soma_cred)
                    
                    combinacoes_validas.append({
                        'STATUS': status,
                        'ADMINISTRADORA': admin,
                        'TIPO': tipo_final,
                        'IDS': ids,
                        'CRÉDITO TOTAL': soma_cred,
                        'ENTRADA TOTAL': soma_ent,
                        'ENTRADA %': entrada_pct * 100,
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
    if texto_site:
        cotas_lidas = extrair_dados_universal(texto_site, "Geral")
        st.info(f"Leitura bruta: {len(cotas_lidas)} linhas identificadas.")
        admins_unicas = sorted(list(set([c['Admin'] for c in cotas_lidas])))
        st.session_state['admins_disponiveis'] = ["Todas"] + admins_unicas
        with st.expander("🕵️‍♂️ Ver o que o robô leu (Diagnóstico)"):
            if cotas_lidas: st.dataframe(pd.DataFrame(cotas_lidas)[['ID','Admin','Tipo','Crédito','Entrada','Parcela','Saldo']])
    else:
        st.session_state['admins_disponiveis'] = ["Todas"]

st.subheader("Filtros JBS")
col_tipo, col_admin = st.columns(2)
tipo_bem = col_tipo.selectbox("Tipo de Bem (O que você copiou?)", ["Imóvel", "Automóvel", "Pesados", "Motos", "Todos"])
admin_filtro = col_admin.selectbox("Administradora", st.session_state['admins_disponiveis'])

c1, c2 = st.columns(2)
min_c = c1.number_input("Crédito Mín (R$)", 0.0, step=1000.0, value=60000.0, format="%.2f")
max_c = c1.number_input("Crédito Máx (R$)", 0.0, step=1000.0, value=710000.0, format="%.2f")
max_e = c2.number_input("Entrada Máx (R$)", 0.0, step=1000.0, value=200000.0, format="%.2f")
max_p = c2.number_input("Parcela Máx (R$)", 0.0, step=100.0, value=4500.0, format="%.2f")
max_k = st.slider("Custo Máx (%)", 0.0, 1.0, 0.55, 0.01)

if st.button("🔍 LOCALIZAR OPORTUNIDADES"):
    if texto_site:
        cotas = extrair_dados_universal(texto_site, tipo_bem)
        if cotas:
            st.session_state.df_resultado = processar_combinacoes(cotas, min_c, max_c, max_e, max_p, max_k, tipo_bem, admin_filtro)
        else:
            st.error("Nenhuma cota lida.")
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
