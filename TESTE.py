import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import numpy as np
import plotly.express as px
import pyodbc
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

ano_vigente = pd.Timestamp.now().year

server = 'BCSQLDELL2'
database = 'SCF'
username = 'RSANTOS'
password = 'R4F43L'
cnxn = pyodbc.connect(
    'DRIVER={SQL Server};SERVER=' + server + ';DATABASE=' + database + ';UID=' + username + ';PWD=' + password)
cursor = cnxn.cursor()

# Configuração da página
st.set_page_config(
    page_title="Sistema Argos",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dados fictícios para demonstração
def load_data():
    data = pd.DataFrame({
        'Data': pd.date_range(start='1/1/2020', periods=100),
        'Valor': np.random.randn(100).cumsum(),
        'Categoria': np.random.choice(['A', 'B', 'C'], size=100)
    })
    return data

data = load_data()

# Definindo as opções de navegação
with st.sidebar:
    selection = option_menu(
        "Menu",
        ["Financeiro", "Registro", "Fiscalização", "Administrativo", "Desenvolvimento Profissional","Indicadores"],
        icons=['currency-dollar', 'file-earmark-text', 'shield-shaded', 'person-workspace', 'briefcase','graph-up'],
        menu_icon="cast",
        default_index=0,
    )

# Função para exibir o dashboard financeiro
def show_financeiro():
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

    # Lista de consultas SQL
    queries = [
        """
        set dateformat dmy 
        select distinct a1.[Numero Guia], a1.[Data Pagamento], a1.[Vlr Pago Total]
        from SFNH03 a1
        where a1.[Data Pagamento] >= '01/01/2020' and a1.[Numero Guia] <> ''
        """,
        """
        set dateformat dmy 
        select distinct a1.[Numero Guia], a1.[Data Pagamento], a1.[Valor Pago] as [Vlr Pago Total]
        from SFNH04 a1
        where a1.[Data Pagamento] >= '01/01/2020' and a1.[Numero Guia] <> ''
        """,
        """
        set dateformat dmy 
        select distinct a1.[Numero Guia], a1.[Data Lote] as [Data Pagamento], a1.[VALOR DO AVISO] as [Vlr Pago Total]
        from SFNH05 a1
        where a1.[Data Lote] >= '01/01/2020' and a1.[Numero Guia] <> '' and a1.[VALOR DO AVISO] > '1'
        """
    ]

    # Executar as consultas e carregar os resultados em dataframes
    dfs = [pd.read_sql(query, cnxn) for query in queries]

    # Fechar a conexão com o banco de dados
    cnxn.close()

    # Concatenar os dataframes
    PAGAMENTOS = pd.concat(dfs)

    # Agrupar e somar os valores pagos por data de pagamento
    PAGAMENTOS = (PAGAMENTOS.drop(['Numero Guia'], axis=1)
                .groupby("Data Pagamento", as_index=False)['Vlr Pago Total']
                .sum())

    # Converter para float para garantir que a formatação será correta
    PAGAMENTOS['Vlr Pago Total'] = PAGAMENTOS['Vlr Pago Total'].astype(float)

    # Converta a coluna 'Data Pagamento' para o tipo datetime
    PAGAMENTOS['Data Pagamento'] = pd.to_datetime(PAGAMENTOS['Data Pagamento'], format='%d/%m/%Y')

    # Adicionar coluna de ano e mês
    PAGAMENTOS['Ano'] = PAGAMENTOS['Data Pagamento'].dt.year
    PAGAMENTOS['Mês'] = PAGAMENTOS['Data Pagamento'].dt.to_period('M')

    # Seleção dos anos disponíveis
    anos_disponiveis = PAGAMENTOS['Ano'].unique()

    # Layout de dashboard com colunas paralelas
    st.title('Visualização da Arrecadação')
    st.write('Comparação de arrecadação por ano')

    colunas = st.columns(len(anos_disponiveis))

    for i, ano in enumerate(anos_disponiveis):
        with colunas[i]:
            st.subheader(f'Ano {ano}')
            PAGAMENTOS_ANO = PAGAMENTOS[PAGAMENTOS['Ano'] == ano]
            PAGAMENTOS_MENSAL = PAGAMENTOS_ANO.groupby('Mês')['Vlr Pago Total'].sum().reset_index()

            # Arredondar os valores para duas casas decimais e converter para milhões
            PAGAMENTOS_MENSAL['Total'] = (PAGAMENTOS_MENSAL['Vlr Pago Total'] / 1e6).round(2)
            PAGAMENTOS_MENSAL = PAGAMENTOS_MENSAL.drop(columns=['Vlr Pago Total'])

            # Formatar a coluna 'Mês' para 'MM/YYYY'
            PAGAMENTOS_MENSAL['Mês'] = PAGAMENTOS_MENSAL['Mês'].dt.strftime('%m/%Y')

            # Criar um gráfico interativo com Plotly
            fig = px.bar(PAGAMENTOS_MENSAL, x='Mês', y='Total',
                        labels={'Total': 'Total (R$ Milhões)', 'Mês': 'Mês'},
                        title=f'Arrecadação Mensal - {ano}')
            
            st.plotly_chart(fig, use_container_width=True)



    PAGAMENTOS_ANUAL = PAGAMENTOS.groupby('Ano')['Vlr Pago Total'].sum().reset_index()
    
    fig = px.bar(PAGAMENTOS_ANUAL, x='Vlr Pago Total', y='Ano', orientation='h',
             labels={'Vlr Pago Total': 'Total Arrecadado (R$)', 'Ano': 'Ano'},
             title='Arrecadação Anual Acumulada')
    st.title('Arrecadação Acumulada - Anual')
    st.plotly_chart(fig, use_container_width=True)
    # # Exibir os dados em tabela
    # st.write('Dados de Arrecadação Mensal')
    # st.dataframe(PAGAMENTOS_MENSAL)
    # Agrupar os dados mensais para calcular a tendência
    arrecadacao_mensal = PAGAMENTOS_ANO.groupby('Mês')['Vlr Pago Total'].sum().reset_index()
    arrecadacao_mensal['Mês'] = arrecadacao_mensal['Mês'].astype(str)

    # Transformar os dados para incluir polinômio de grau 3 (exemplo)
    X = np.arange(len(arrecadacao_mensal)).reshape(-1, 1)
    y = arrecadacao_mensal['Vlr Pago Total'].values.reshape(-1, 1)

    poly = PolynomialFeatures(degree=3)  # Grau do polinômio ajustável
    X_poly = poly.fit_transform(X)

    # Ajustar o modelo de regressão polinomial
    model = LinearRegression().fit(X_poly, y)

    # Prever a tendência até dezembro de 2024
    meses_futuros = np.arange(len(arrecadacao_mensal), len(arrecadacao_mensal) + 8).reshape(-1, 1)
    meses_futuros_poly = poly.transform(meses_futuros)
    tendencia_futura = model.predict(meses_futuros_poly)

    # Criar array para a tendência completa
    tendencia_passada = model.predict(X_poly).reshape(-1)
    tendencia_completa = np.concatenate((tendencia_passada, tendencia_futura.reshape(-1)))

    # Adicionar a tendência ao dataframe
    arrecadacao_mensal['Tendência'] = tendencia_completa[:len(arrecadacao_mensal)]

    # Criar o gráfico de linha de tendência usando Plotly
    fig = go.Figure()

    # Adicionar os dados de arrecadação mensal
    fig.add_trace(go.Scatter(x=arrecadacao_mensal['Mês'], y=arrecadacao_mensal['Vlr Pago Total'],
                            mode='lines+markers', name='Arrecadação Mensal'))

    # Adicionar a linha de tendência
    fig.add_trace(go.Scatter(x=arrecadacao_mensal['Mês'], y=arrecadacao_mensal['Tendência'],
                            mode='lines', name='Tendência'))

    # Configurar o layout do gráfico
    fig.update_layout(title=f'Tendência de Arrecadação Mensal - Previsão até Dezembro de 2024',
                    xaxis_title='Mês',
                    yaxis_title='Total Arrecadado (R$)',
                    legend=dict(x=0, y=1, traceorder='normal'))

    # Exibir o gráfico no Streamlit
    st.title('Tendência de Arrecadação Anual')
    st.plotly_chart(fig, use_container_width=True)


    # Seção para análise do estoque da dívida
    # Supondo que você já tem a conexão com o banco de dados configurada
    # e as consultas SQL estão em uma lista chamada `queries`
    queries = [
        """
        set dateformat dmy
        select 
            a1.[Data Vencimento] as [Data Vencimento], 
            a1.[Valor Total] as [Valor Total] 
        from VIEW_SFN_SFNA01_CORRIGIDO a1, SFNT108 a2
        where 
            a1.[Codigo Debito] = a2.[Codigo Debito]  
            and a1.Parcela <> 0 
            and a1.TotalParcelas <> 0 
        order by a1.[Data Vencimento]
        """,
        """
        set dateformat dmy
    select 
        a1.[Data Vencimento] as [Data Vencimento], 
        a1.[Valor Total] as [Valor Total] 
    from VIEW_SFN_SFNA02_CORRIGIDO a1, SFNT108 a2
    where 
        a1.[Codigo Debito] = a2.[Codigo Debito]  
        and a1.Parcela <> 0 
        and a1.TotalParcelas <> 0 
    order by a1.[Data Vencimento]
        """,
        """
        set dateformat dmy
    select 
        a1.[Data Vencimento] as [Data Vencimento], 
        a1.[Valor Total] as [Valor Total] 
    from VIEW_SFN_SFNA04_CORRIGIDO a1, SFNT108 a2
    where 
        a1.[Codigo Debito] = a2.[Codigo Debito]  
        and a1.Parcela <> 0 
        and a1.TotalParcelas <> 0 
    order by a1.[Data Vencimento]
        """,
        """set dateformat dmy
    select 
        a1.[Data Vencimento] as [Data Vencimento], 
        a1.[Valor Total] as [Valor Total] 
    from VIEW_SFN_SFNA05_CORRIGIDO a1, SFNT108 a2
    where 
        a1.[Codigo Debito] = a2.[Codigo Debito]  
        and a1.Parcela <> 0 
        and a1.TotalParcelas <> 0 
    order by a1.[Data Vencimento]"""
    ]
    # Vamos executar as consultas e obter os dados
    dados_totais = []

    # Exemplo de conexão com o banco de dados (adaptar conforme necessário)
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

    for query in queries:
        dados_query = pd.read_sql(query, cnxn)
        dados_totais.append(dados_query)

    # Concatenar todos os resultados em um único dataframe
    dados_completos = pd.concat(dados_totais)

    # Limpar e preparar os dados (opcional, dependendo da limpeza necessária)

    # Agrupar por mês e calcular o total de recebimento por mês
    dados_completos['Data Vencimento'] = pd.to_datetime(dados_completos['Data Vencimento'], format='%d/%m/%Y')
    dados_completos['Mês'] = dados_completos['Data Vencimento'].dt.to_period('M')
    recebimento_mensal = dados_completos.groupby('Mês')['Valor Total'].sum().reset_index()

   # Converter o período para string no formato desejado (exemplo: 'YYYY-MM')
    recebimento_mensal['Mês'] = recebimento_mensal['Mês'].dt.strftime('%Y-%m')

    # Criar o gráfico de linha com Plotly
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=recebimento_mensal['Mês'], y=recebimento_mensal['Valor Total'],
                            mode='lines+markers', name='Recebimento Mensal'))

    fig.update_layout(title='Previsão de Recebimento Mensal',
                    xaxis_title='Mês',
                    yaxis_title='Total Recebido (R$)',
                    legend=dict(x=0, y=1, traceorder='normal'))

    # Exibir o gráfico no Streamlit
    st.title('Previsão de Recebimento Mensal')
    st.plotly_chart(fig, use_container_width=True)








    # Seção para análise do estoque da dívida

    # Consulta para análise do estoque da dívida
    query_divida = """
    set dateformat dmy
    select 
        a1.[Data Vencimento] as [Data Vencimento], 
        a1.[Data Execucao Judicial] as [Data Execucao], 
        a1.[Valor Originario] as [Valor Originario], 
        a1.[Valor Total] as [Valor Total] 
    from VIEW_SFN_SFNA01_CORRIGIDO a1, SFNT108 a2
    where 
        a1.[Codigo Debito] = a2.[Codigo Debito]  
        and a1.Parcela = 0 
        and a1.TotalParcelas = 0 
    order by a1.[Data Vencimento]
    """

    # Conectar novamente para a nova consulta
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)
    df_divida = pd.read_sql(query_divida, cnxn)
    cnxn.close()

    # Processar os dados da dívida
    df_divida['Data Vencimento'] = pd.to_datetime(df_divida['Data Vencimento'], format='%d/%m/%Y')
    df_divida['Ano Vencimento'] = df_divida['Data Vencimento'].dt.year

    # Agrupar por ano de vencimento e calcular o total e quantidade de débitos
    divida_ano = df_divida.groupby('Ano Vencimento').agg(
        Quantidade=('Valor Total', 'size'),
        Total=('Valor Total', 'sum')
    ).reset_index()

    # Arredondar os valores para duas casas decimais e converter para milhões
    divida_ano['Total em Milhões'] = (divida_ano['Total'] / 1e6).round(2)
    divida_ano['Quantidade'] = divida_ano['Quantidade'].apply(lambda x: f"{x:,.0f}".replace(',', '.'))

    # Remover formatação do ano
    divida_ano['Ano Vencimento'] = divida_ano['Ano Vencimento'].astype(str)

    # Criar um gráfico de barras para o estoque da dívida
    fig = px.bar(divida_ano, x='Ano Vencimento', y='Total em Milhões',
                 labels={'Total em Milhões': 'Total em Milhões (R$)', 'Ano Vencimento': 'Ano'},
                 title='Estoque da Dívida por Ano')

    # Exibir o gráfico
    st.title('Análise do Estoque da Dívida')
    st.plotly_chart(fig, use_container_width=True)

 

# Função para exibir o dashboard de registro
def show_registro():
    st.title("Dashboard de Registro")
    st.write("Aqui estão os dados de registro...")

    # Configuração da conexão com o banco de dados
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

    # Consulta SQL para traduzir a situação cadastral e obter o sexo dos profissionais
    sql_query = """
    SELECT
        CASE 
            WHEN SCDA01.[Situacao Cadastral] = 1 THEN 'Ativo'
            WHEN SCDA01.[Situacao Cadastral] IN (2, 99) THEN 'Baixado por Solicitação'
            WHEN SCDA01.[Situacao Cadastral] = 9 THEN 'Cancelado por Falecimento'
            WHEN SCDA01.[Situacao Cadastral] = 3 THEN 'Baixado por Transferência'
            WHEN SCDA01.[Situacao Cadastral] = 5 THEN 'Baixado por Vencimento'
            WHEN SCDA01.[Situacao Cadastral] IN (7, 8) THEN 'Cancelamento Ex-Officio'
            WHEN SCDA01.[Situacao Cadastral] = 33 THEN 'Cassado'
            WHEN SCDA01.[Situacao Cadastral] = 6 THEN 'Suspenso'
            ELSE 'Situação Desconhecida'
        END AS [Situacao Cadastral],
        CASE
            WHEN SCDA01.[Sexo] = 2 THEN 'Feminino'
            WHEN SCDA01.[Sexo] = 1 THEN 'Masculino'
        END AS Sexo,
        CASE
            WHEN SCDA01.[Categoria] = 2 THEN 'Tecnico'
            WHEN SCDA01.[Categoria] = 1 THEN 'Contador'
        END AS Categoria,
        COUNT(*) AS Quantidade
    FROM SCDA01
    WHERE SCDA01.[Tipo Situacao] <> 'S'
    GROUP BY SCDA01.[Situacao Cadastral], SCDA01.[Sexo],SCDA01.[Categoria];
    """

    # Executar a consulta SQL e obter os resultados como DataFrame
    registros = pd.read_sql(sql_query, cnxn)
    
    # Fechar a conexão com o banco de dados
    cnxn.close()
   # Configuração da página do Streamlit
    st.title('Quadro de Profissionais - Situação Cadastral e Sexo')

    # Executar a consulta para obter os dados agrupados
    df_agrupado = registros

    # Pivotando os dados para organizar em 4 colunas
    df_pivot = df_agrupado.pivot_table(index='Situacao Cadastral', columns='Sexo', values='Quantidade', aggfunc='sum').reset_index()

    # Verificar e ajustar as colunas conforme necessário
    if 'Feminino' in df_pivot.columns:
        df_pivot.rename(columns={'Feminino': 'Total Feminino'}, inplace=True)
    else:
        df_pivot['Total Feminino'] = 0

    if 'Masculino' in df_pivot.columns:
        df_pivot.rename(columns={'Masculino': 'Total Masculino'}, inplace=True)
    else:
        df_pivot['Total Masculino'] = 0


    # Adicionar a coluna com a soma total
    df_pivot=df_pivot.fillna(0)
    df_pivot['Total Quantitativo'] = df_pivot['Total Feminino'] + df_pivot['Total Masculino']
    df_pivot['Total Feminino'] = df_pivot['Total Feminino'].apply(lambda x: '{:,.0f}'.format(x).replace(',', '.'))
    df_pivot['Total Masculino'] = df_pivot['Total Masculino'].apply(lambda x: '{:,.0f}'.format(x).replace(',', '.'))
    df_pivot['Total Quantitativo'] = df_pivot['Total Quantitativo'].apply(lambda x: '{:,.0f}'.format(x).replace(',', '.'))

    # Exibir os dados agrupados em uma tabela no Streamlit
    st.write("Dados Agrupados por Situação Cadastral e Sexo:")
    st.write(df_pivot)

 # Configuração da conexão com o banco de dados
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

    # Consulta SQL para traduzir a situação cadastral e obter o sexo dos profissionais
    sql_query = """
    
        SELECT
            CASE 
                WHEN SCDA02.[Situacao Cadastral] = 1 THEN 'Ativo'
                WHEN SCDA02.[Situacao Cadastral] IN (2, 99) THEN 'Baixado por Solicitação'
                WHEN SCDA02.[Situacao Cadastral] = 9 THEN 'Cancelado por Falecimento'
                WHEN SCDA02.[Situacao Cadastral] = 3 THEN 'Baixado por Transferência'
                WHEN SCDA02.[Situacao Cadastral] = 5 THEN 'Baixado por Vencimento'
                WHEN SCDA02.[Situacao Cadastral] IN (7, 8) THEN 'Cancelamento Ex-Oficcio'
                WHEN SCDA02.[Situacao Cadastral] = 33 THEN 'Cassado'
                WHEN SCDA02.[Situacao Cadastral] = 6 THEN 'Suspenso'
                ELSE 'Situação Desconhecida'
            END AS [Situacao Cadastral],
            CASE 
                WHEN SCDA02.[Tipo de Sociedade] = 5 THEN 'Auditoria Independente'
                WHEN SCDA02.[Tipo de Sociedade] = 6 THEN 'Auditoria e Contabilidade'
                WHEN SCDA02.[Tipo de Sociedade] IN (3,1000, 1004,1005,1006,1008) THEN 'Baixado por Solicitação'
                WHEN SCDA02.[Tipo de Sociedade] = 1001 THEN 'Sociedade Empresaria LTDA'
                WHEN SCDA02.[Tipo de Sociedade] = 1002 THEN 'Sociedade Simples Pura'
                WHEN SCDA02.[Tipo de Sociedade] = 1003 THEN 'Sociedade Simples Limitada'
                WHEN SCDA02.[Tipo de Sociedade] in (0,4) THEN 'Nao Informado'
                WHEN SCDA02.[Tipo de Sociedade] = 7 THEN 'PRAZO 180 DIAS ART.1033 CC'
                WHEN SCDA02.[Tipo de Sociedade] = 1 THEN 'Sociedade Profissional'
                WHEN SCDA02.[Tipo de Sociedade] = 2 THEN 'Sociedade Mista'
                ELSE 'Situação Desconhecida'
            END AS [Tipo de Sociedade],
            COUNT(*) AS Quantidade
        FROM SCDA02
        WHERE SCDA02.[Tipo Situacao] <> 'S'
        GROUP BY SCDA02.[Situacao Cadastral], SCDA02.[Tipo de Sociedade];
    """

    # Executar a consulta SQL e obter os resultados como DataFrame
    sociedades = pd.read_sql(sql_query, cnxn)
    sociedades.fillna(0)
    # Fechar a conexão com o banco de dados
    cnxn.close()
   # Configuração da página do Streamlit
    st.title('Quadro de Sociedades - Situação Cadastral e Tipo')


    # Pivotando os dados para organizar as colunas
    df_pivot2 = sociedades.pivot_table(index='Situacao Cadastral', columns='Tipo de Sociedade', values='Quantidade', aggfunc='sum').reset_index()
    df_pivot2['Total Quantitativo'] = df_pivot2.drop(columns=['Situacao Cadastral']).sum(axis=1)
    # Formatar as colunas de total para milhar separado por ponto e sem casas decimais
    for col in df_pivot2.columns:
        if col != 'Situacao Cadastral':
            df_pivot2[col] = df_pivot2[col].apply(lambda x: '{:,.0f}'.format(x).replace(',', '.') if pd.notnull(x) else x)
    df_pivot2=df_pivot2.fillna(0)
    # Exibir os dados agrupados em uma tabela no Streamlit
    st.write("Dados Agrupados por Situação Cadastral e Tipo de Sociedade:")
    st.write(df_pivot2)

    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

        # Consulta SQL
    sql_query = """
    SELECT SCDA04.[Dt Diplomacao], COUNT(SCDA04.[Dt Diplomacao]) AS Quantidade
    FROM SCDA04
    WHERE SCDA04.[Tipo Situacao] = 'E'
        AND SCDA04.[Situacao Cadastral] = 1
        AND SCDA04.[Classe] = 3
    GROUP BY SCDA04.[Dt Diplomacao]
    """

    # Executar a consulta SQL e obter os resultados como DataFrame
    df = pd.read_sql(sql_query, cnxn)

    # Fechar a conexão com o banco de dados
    cnxn.close()

    # Configuração da página do Streamlit
    st.title('Estudantes')
    st.subheader('Quadro de Estudantes Ativos por data de diplomação')
    df = df.sort_values(by='Dt Diplomacao').reset_index(drop=True)
    df['Dt Diplomacao'] = pd.to_datetime(df['Dt Diplomacao'], format='%Y-%m-%d', errors='coerce').dt.strftime('%d/%m/%Y')

    st.write(df)

    # Exibir gráfico de barras com Plotly
    import plotly.express as px

    fig = px.bar(df, x='Dt Diplomacao', y='Quantidade', title='Quantidade de Diplomações por Data')
    st.plotly_chart(fig)



    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)
    
    queries = [
    """
    SELECT 
        CASE 
            WHEN SCDA51.[Delegacia] IN (001, 028, 029, 030, 031, 034) THEN 'RIO DE JANEIRO'
            WHEN SCDA51.[Delegacia] = 003 THEN 'NITEROI'
            WHEN SCDA51.[Delegacia] = 005 THEN 'MACAE'
            WHEN SCDA51.[Delegacia] = 006 THEN 'CAMPOS DOS GOITACAZES'
            WHEN SCDA51.[Delegacia] = 007 THEN 'ITAPERUNA'
            WHEN SCDA51.[Delegacia] = 009 THEN 'NOVA FRIBURGO'
            WHEN SCDA51.[Delegacia] = 011 THEN 'PETROPOLIS'
            WHEN SCDA51.[Delegacia] = 012 THEN 'TRES RIOS'
            WHEN SCDA51.[Delegacia] = 013 THEN 'DUQUE DE CAXIAS'
            WHEN SCDA51.[Delegacia] = 014 THEN 'NOVA IGUAÇU'
            WHEN SCDA51.[Delegacia] = 015 THEN 'ANGRA DOS REIS'
            WHEN SCDA51.[Delegacia] = 017 THEN 'RESENDE'
            WHEN SCDA51.[Delegacia] = 018 THEN 'VOLTA REDONDA'
            WHEN SCDA51.[Delegacia] = 020 THEN 'BARRA DO PIRAÍ'
            WHEN SCDA51.[Delegacia] = 021 THEN 'RIO BONITO'
            WHEN SCDA51.[Delegacia] = 022 THEN 'TERESOPOLIS'
            WHEN SCDA51.[Delegacia] = 024 THEN 'SAO JOAO DE MERITI'
            WHEN SCDA51.[Delegacia] = 025 THEN 'CABO FRIO'
            WHEN SCDA51.[Delegacia] = 026 THEN 'SAO GONÇALO'
            WHEN SCDA51.[Delegacia] = 032 THEN 'ARARUAMA'
            WHEN SCDA51.[Delegacia] = 033 THEN 'ITABORAI'
            WHEN SCDA51.[Delegacia] = 035 THEN 'MANGARATIBA'
            WHEN SCDA51.[Delegacia] = 999 THEN 'OUTROS ESTADOS'
            ELSE SCDA51.[Delegacia]
        END AS Delegacia,
        COUNT(*) AS [Profissionais]
    FROM SCDA51
    WHERE
        SCDA51.[Num. Registro] IN (
            SELECT DISTINCT SCDA01.[Num. Registro] 
            FROM SCDA01
            WHERE 
                SCDA01.[Situacao Cadastral] = '1' 
                AND SCDA01.[Tipo Situacao] <> 'S'
        ) 
        AND SCDA51.[Endereco Ativo] = 'SIM'
        AND SCDA51.[Endereco Correspondencia] = 'SIM'
    GROUP BY 
        CASE 
            WHEN SCDA51.[Delegacia] IN (001, 028, 029, 030, 031, 034) THEN 'RIO DE JANEIRO'
            WHEN SCDA51.[Delegacia] = 003 THEN 'NITEROI'
            WHEN SCDA51.[Delegacia] = 005 THEN 'MACAE'
            WHEN SCDA51.[Delegacia] = 006 THEN 'CAMPOS DOS GOITACAZES'
            WHEN SCDA51.[Delegacia] = 007 THEN 'ITAPERUNA'
            WHEN SCDA51.[Delegacia] = 009 THEN 'NOVA FRIBURGO'
            WHEN SCDA51.[Delegacia] = 011 THEN 'PETROPOLIS'
            WHEN SCDA51.[Delegacia] = 012 THEN 'TRES RIOS'
            WHEN SCDA51.[Delegacia] = 013 THEN 'DUQUE DE CAXIAS'
            WHEN SCDA51.[Delegacia] = 014 THEN 'NOVA IGUAÇU'
            WHEN SCDA51.[Delegacia] = 015 THEN 'ANGRA DOS REIS'
            WHEN SCDA51.[Delegacia] = 017 THEN 'RESENDE'
            WHEN SCDA51.[Delegacia] = 018 THEN 'VOLTA REDONDA'
            WHEN SCDA51.[Delegacia] = 020 THEN 'BARRA DO PIRAÍ'
            WHEN SCDA51.[Delegacia] = 021 THEN 'RIO BONITO'
            WHEN SCDA51.[Delegacia] = 022 THEN 'TERESOPOLIS'
            WHEN SCDA51.[Delegacia] = 024 THEN 'SAO JOAO DE MERITI'
            WHEN SCDA51.[Delegacia] = 025 THEN 'CABO FRIO'
            WHEN SCDA51.[Delegacia] = 026 THEN 'SAO GONÇALO'
            WHEN SCDA51.[Delegacia] = 032 THEN 'ARARUAMA'
            WHEN SCDA51.[Delegacia] = 033 THEN 'ITABORAI'
            WHEN SCDA51.[Delegacia] = 035 THEN 'MANGARATIBA'
            WHEN SCDA51.[Delegacia] = 999 THEN 'OUTROS ESTADOS'
            ELSE SCDA51.[Delegacia]
        END;
    """,
    """
    SELECT 
        CASE 
            WHEN SCDA52.[Delegacia] IN (001, 028, 029, 030, 031, 034) THEN 'RIO DE JANEIRO'
            WHEN SCDA52.[Delegacia] = 003 THEN 'NITEROI'
            WHEN SCDA52.[Delegacia] = 005 THEN 'MACAE'
            WHEN SCDA52.[Delegacia] = 006 THEN 'CAMPOS DOS GOITACAZES'
            WHEN SCDA52.[Delegacia] = 007 THEN 'ITAPERUNA'
            WHEN SCDA52.[Delegacia] = 009 THEN 'NOVA FRIBURGO'
            WHEN SCDA52.[Delegacia] = 011 THEN 'PETROPOLIS'
            WHEN SCDA52.[Delegacia] = 012 THEN 'TRES RIOS'
            WHEN SCDA52.[Delegacia] = 013 THEN 'DUQUE DE CAXIAS'
            WHEN SCDA52.[Delegacia] = 014 THEN 'NOVA IGUAÇU'
            WHEN SCDA52.[Delegacia] = 015 THEN 'ANGRA DOS REIS'
            WHEN SCDA52.[Delegacia] = 017 THEN 'RESENDE'
            WHEN SCDA52.[Delegacia] = 018 THEN 'VOLTA REDONDA'
            WHEN SCDA52.[Delegacia] = 020 THEN 'BARRA DO PIRAÍ'
            WHEN SCDA52.[Delegacia] = 021 THEN 'RIO BONITO'
            WHEN SCDA52.[Delegacia] = 022 THEN 'TERESOPOLIS'
            WHEN SCDA52.[Delegacia] = 024 THEN 'SAO JOAO DE MERITI'
            WHEN SCDA52.[Delegacia] = 025 THEN 'CABO FRIO'
            WHEN SCDA52.[Delegacia] = 026 THEN 'SAO GONÇALO'
            WHEN SCDA52.[Delegacia] = 032 THEN 'ARARUAMA'
            WHEN SCDA52.[Delegacia] = 033 THEN 'ITABORAI'
            WHEN SCDA52.[Delegacia] = 035 THEN 'MANGARATIBA'
            WHEN SCDA52.[Delegacia] = 999 THEN 'OUTROS ESTADOS'
            ELSE SCDA52.[Delegacia]
        END AS Delegacia,
        COUNT(*) AS [Empresas]
    FROM SCDA52
    WHERE
        SCDA52.[Num. Registro] IN (
            SELECT DISTINCT SCDA02.[Num. Registro] 
            FROM SCDA02
            WHERE 
                SCDA02.[Situacao Cadastral] = '1' 
                AND SCDA02.[Tipo Situacao] <> 'S'
        ) 
        AND SCDA52.[Endereco Ativo] = 'SIM'
        AND SCDA52.[Endereco Correspondencia] = 'SIM'
    GROUP BY 
        CASE 
            WHEN SCDA52.[Delegacia] IN (001, 028, 029, 030, 031, 034) THEN 'RIO DE JANEIRO'
            WHEN SCDA52.[Delegacia] = 003 THEN 'NITEROI'
            WHEN SCDA52.[Delegacia] = 005 THEN 'MACAE'
            WHEN SCDA52.[Delegacia] = 006 THEN 'CAMPOS DOS GOITACAZES'
            WHEN SCDA52.[Delegacia] = 007 THEN 'ITAPERUNA'
            WHEN SCDA52.[Delegacia] = 009 THEN 'NOVA FRIBURGO'
            WHEN SCDA52.[Delegacia] = 011 THEN 'PETROPOLIS'
            WHEN SCDA52.[Delegacia] = 012 THEN 'TRES RIOS'
            WHEN SCDA52.[Delegacia] = 013 THEN 'DUQUE DE CAXIAS'
            WHEN SCDA52.[Delegacia] = 014 THEN 'NOVA IGUAÇU'
            WHEN SCDA52.[Delegacia] = 015 THEN 'ANGRA DOS REIS'
            WHEN SCDA52.[Delegacia] = 017 THEN 'RESENDE'
            WHEN SCDA52.[Delegacia] = 018 THEN 'VOLTA REDONDA'
            WHEN SCDA52.[Delegacia] = 020 THEN 'BARRA DO PIRAÍ'
            WHEN SCDA52.[Delegacia] = 021 THEN 'RIO BONITO'
            WHEN SCDA52.[Delegacia] = 022 THEN 'TERESOPOLIS'
            WHEN SCDA52.[Delegacia] = 024 THEN 'SAO JOAO DE MERITI'
            WHEN SCDA52.[Delegacia] = 025 THEN 'CABO FRIO'
            WHEN SCDA52.[Delegacia] = 026 THEN 'SAO GONÇALO'
            WHEN SCDA52.[Delegacia] = 032 THEN 'ARARUAMA'
            WHEN SCDA52.[Delegacia] = 033 THEN 'ITABORAI'
            WHEN SCDA52.[Delegacia] = 035 THEN 'MANGARATIBA'
            WHEN SCDA52.[Delegacia] = 999 THEN 'OUTROS ESTADOS'
            ELSE SCDA52.[Delegacia]
        END;
    """
]

    # Executando consultas e carregando resultados em DataFrames
    df_profissionais = pd.read_sql_query(queries[0], cnxn)
    df_empresas = pd.read_sql_query(queries[1], cnxn)

    # Mesclando os DataFrames com base na coluna 'Delegacia'
    df_combined = pd.merge(df_profissionais, df_empresas, on='Delegacia', how='outer')

    # Exibindo resultados com Streamlit
    st.title('Quantidade de Profissionais e Empresas por Delegacia')
   

    fig = px.bar(df_combined, x='Delegacia', y=['Profissionais', 'Empresas'], 
                barmode='group', title='Profissionais e Empresas por Delegacia')
    st.plotly_chart(fig)


     # Configuração da conexão com o banco de dados
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

    # Consulta SQL ajustada
    sql_query = """
    SELECT
        CASE 
            WHEN SPR..SPRA03.[Codigo Assunto] = 3026 THEN 'REGISTRO CADASTRAL DEFINITIVO SOCIEDADE'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3017 THEN 'REGISTRO CADASTRAL DEFINITIVO - EMPRESÁRIO'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3005 THEN 'ALTERAÇÃO DE REGISTRO (NOME) - PF'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3029 THEN 'ALTERAÇÃO DE REGISTRO CADASTRAL - SOCIEDADE'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3023 THEN 'BAIXA DE REGISTRO PROFISSIONAL'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3007 THEN 'CANCELAMENTO DE REGISTRO(POR FALECIMENTO) - PF'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3006 THEN 'RESTABELECIMENTO DE REGISTRO PROFISSIONAL'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3001 THEN 'REGISTRO DEFINITIVO ORIGINÁRIO - PF'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3032 THEN 'CANCELAMENTO REGISTRO CADASTRAL - SOCIEDADE'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3031 THEN 'BAIXA DE REGISTRO CADASTRAL SOCIEDADE'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3022 THEN 'CANCELAMENTO(FALECIMENTO DO TITULAR)- EMPRESÁRIO'
            WHEN SPR..SPRA03.[Codigo Assunto] = 3020 THEN 'ALTERAÇÃO DE REGISTRO CADASTRAL - EMPRESÁRIO'
            ELSE 'Assunto Desconhecido'
        END AS [Codigo Assunto],
        SPR..SPRA03.[Dt Entrada],
        DATEDIFF(day, SPR..SPRA03.[Dt Entrada], GETDATE()) AS [Dias em Aberto]
    FROM SPR..SPRA03
    WHERE SPR..SPRA03.[Tipo Proc.] = 'ADM'
      AND SPR..SPRA03.[Localizacao Atual] = 7
      AND SPR..SPRA03.[Codigo Situacao] IN (3001, 3035);
    """

    # Executar a consulta SQL e obter os resultados como DataFrame
    processos = pd.read_sql(sql_query, cnxn)

    # Fechar a conexão com o banco de dados
    cnxn.close()

     # Configuração da página do Streamlit
    st.title('Processos - Quantidade e Tempo de Abertura')

    # Executar a consulta para obter os dados
    

    # Agrupar os dados por Código de Assunto e calcular a quantidade de processos e o tempo médio de aberto
    processos = processos.groupby('Codigo Assunto').agg({
        'Dt Entrada': 'count',
        'Dias em Aberto': 'mean'
    }).reset_index()

    # Renomear as colunas para ficar mais claro
    processos.columns = ['Codigo Assunto', 'Quantidade de Processos', 'Tempo Médio em Aberto (Dias)']

      # Arredondar o tempo médio em aberto para números inteiros
    processos['Tempo Médio em Aberto (Dias)'] = processos['Tempo Médio em Aberto (Dias)'].round().astype(int)

    # Formatar as colunas de total para milhar separado por ponto e sem casas decimais
    processos['Quantidade de Processos'] = processos['Quantidade de Processos'].apply(lambda x: '{:,.0f}'.format(x).replace(',', '.'))

    # Exibir os dados em uma tabela no Streamlit
    st.write("Quantidade de Processos por Código de Assunto e Tempo Médio em Aberto: Em Analise ou Exigência")
    st.write(processos)


# Função para exibir o dashboard de fiscalização
def show_fiscalizacao():
    st.title("Dashboard de Fiscalização")
    st.write("Aqui estão os dados de fiscalização...")






    fig = px.scatter(data, x='Data', y='Valor', color='Categoria', title='Inspeções ao longo do tempo')
    st.plotly_chart(fig)

# Função para exibir o dashboard administrativo
def show_administrativo(data):
    st.title("Dashboard Administrativo")
    st.write("Aqui estão os dados administrativos...")

    fig = px.box(data, x='Categoria', y='Valor', title='Resumo Administrativo')
    st.plotly_chart(fig)

# Função para exibir o dashboard de desenvolvimento profissional
def show_desenvolvimento_profissional(data):
    st.title("Dashboard de Desenvolvimento Profissional")
    st.write("Aqui estão os dados de desenvolvimento profissional...")

    fig = px.bar(data, x='Categoria', y='Valor', title='Desenvolvimento por Categoria')
    st.plotly_chart(fig)
# Função para exibir o dashboard de desenvolvimento profissional
def show_indicadores(data):
    st.title("Dashboard de Indicadores")
    st.write("Aqui estão os dados de Indicadores...")

        # Defina a conexão com o banco de dados
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)

    # Consultas SQL
    query_ativos = """
    select 
        a1.[Num. Registro] as Registro 
    from SCDA01 a1 
    where 
        a1.[Tipo Situacao] <> 'S' and
        a1.[Situacao Cadastral]='1'
    order by a1.[Num. Registro]
    """
    df_ativos = pd.read_sql(query_ativos, cnxn)

    query_devedores = """
    select 
        a1.[Num. Registro] as Registro, 
        COUNT(*) as Total
    from VIEW_SFN_SFNA01_CORRIGIDO a1
    where 
        a1.[Parcela] = '0' 
    group by a1.[Num. Registro]
    """
    df_devedores = pd.read_sql(query_devedores, cnxn)

    query_ativos_soc = """
    select 
        a1.[Num. Registro] as Registro 
    from SCDA02 a1 
    where 
        a1.[Tipo Situacao] <> 'S' and
        a1.[Situacao Cadastral]='1'
    order by a1.[Num. Registro]
    """
    df_ativos_soc = pd.read_sql(query_ativos_soc, cnxn)

    query_devedores_soc = """
    select 
        a1.[Num. Registro] as Registro, 
        COUNT(*) as Total
    from VIEW_SFN_SFNA02_CORRIGIDO a1
    where 
        a1.[Parcela] = '0' 
    group by a1.[Num. Registro]
    """
    df_devedores_soc = pd.read_sql(query_devedores_soc, cnxn)
    cnxn.close()

    # Processamento de dados
    total_ativos_devedores = len(df_devedores[df_devedores['Registro'].isin(df_ativos['Registro'])])
    total_ativos = len(df_ativos['Registro'])

    total_ativos_devedores_soc = len(df_devedores_soc[df_devedores_soc['Registro'].isin(df_ativos_soc['Registro'])])
    total_ativos_soc = len(df_ativos_soc['Registro'])

    # Cálculo do percentual
    percentual_profissionais = (total_ativos_devedores / total_ativos) * 100 if total_ativos > 0 else 0
    percentual_sociedades = (total_ativos_devedores_soc / total_ativos_soc) * 100 if total_ativos_soc > 0 else 0

    # Criação do DataFrame final
    inadimplencia = pd.DataFrame({
        'Categoria': ['Profissionais', 'Sociedades'],
        'ATIVOS DEVEDORES': [total_ativos_devedores, total_ativos_devedores_soc],
        'TOTAL ATIVOS': [total_ativos, total_ativos_soc],
        'PERCENTUAL': [percentual_profissionais, percentual_sociedades]
    })

    # Formatação das colunas
    inadimplencia['ATIVOS DEVEDORES'] = inadimplencia['ATIVOS DEVEDORES'].apply(lambda x: f"{x:,.0f}".replace(',', '.'))
    inadimplencia['TOTAL ATIVOS'] = inadimplencia['TOTAL ATIVOS'].apply(lambda x: f"{x:,.0f}".replace(',', '.'))
    inadimplencia['PERCENTUAL'] = inadimplencia['PERCENTUAL'].apply(lambda x: f"{x:.2f}%")

    # Exibição dos indicadores
    st.title('Inadimplencia')
    st.dataframe(inadimplencia)

    

        # Dados de exemplo (substitua pelos seus dados reais)
    ativos_2023_profissionais = 54408  # Número de ativos em 2023 (exemplo)
    ativos_2023_sociedades=7006

    # Cálculo do percentual de crescimento
    percentual_crescimento_profissionais = ((total_ativos - ativos_2023_profissionais) / ativos_2023_profissionais) * 100
    percentual_crescimento_sociedades = ((total_ativos_soc - ativos_2023_sociedades) / ativos_2023_sociedades) * 100

    # Criação do DataFrame
    registro = pd.DataFrame({
        'Ativos 2023': [ativos_2023_profissionais, ativos_2023_sociedades],
        'Total de Ativos': [total_ativos, total_ativos_soc],
        'Percentual de Crescimento': [f"{percentual_crescimento_profissionais:.2f}%", f"{percentual_crescimento_sociedades:.2f}%"]
    }, index=['Profissional', 'Sociedade'])

    registro['Ativos 2023'] = registro['Ativos 2023'].apply(lambda x: f"{x:,.0f}".replace(',', '.'))
    registro['Total de Ativos'] = registro['Total de Ativos'].apply(lambda x: f"{x:,.0f}".replace(',', '.'))
    # Exibição dos indicadores
    st.title('Crescimento de Registros')
    st.dataframe(registro)




# Lógica de navegação
if selection == "Financeiro":
    show_financeiro()
elif selection == "Registro":
    show_registro()
elif selection == "Fiscalização":
    show_fiscalizacao()
elif selection == "Administrativo":
    show_administrativo(data)
elif selection == "Desenvolvimento Profissional":
    show_desenvolvimento_profissional(data)
elif selection == "Indicadores":
    show_indicadores(data)