import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import os


# Variáveis que guardam o estado atual da aplicação.
# Como a interface é simples, elas ficam compartilhadas entre os botões e os gráficos.
arquivo_path = ""
dados = None
canvas_grafico = None
K_estimado = None
L_estimado = None
T_estimado = None
degrau = None

# Evita que o Matplotlib tente abrir uma janela própria fora do Tkinter.
plt.ioff()


def selecionar_arquivo():
    global arquivo_path

    # Abre a janela para o usuário escolher o CSV com a resposta da planta.
    caminho = filedialog.askopenfilename(
        title="Selecione um arquivo CSV",
        filetypes=[("Arquivo CSV", "*.csv")],
    )

    if caminho:
        arquivo_path = caminho
        label_arquivo_valor.config(text=arquivo_path)


def modelo_fopdt(t, K, L, T, du):
    # Modelo de primeira ordem com atraso (FOPDT).
    # Antes do atraso L a saída fica em zero; depois disso ela cresce exponencialmente.
    y = np.zeros_like(t, dtype=float)

    for i in range(len(t)):
        if t[i] >= L:
            y[i] = K * du * (1 - np.exp(-(t[i] - L) / T))
        else:
            y[i] = 0.0

    return y


def carregar_dados():
    global dados, degrau

    try:
        if arquivo_path == "":
            messagebox.showerror("Erro", "Selecione um arquivo CSV.")
            return

        # Aceita tanto vírgula quanto ponto nos campos numéricos.
        ts = float(entry_ts.get().strip().replace(",", "."))
        degrau = float(entry_degrau.get().strip().replace(",", "."))

        if ts <= 0:
            messagebox.showerror("Erro", "Ts deve ser maior que zero.")
            return

        if degrau == 0:
            messagebox.showerror("Erro", "A amplitude do degrau não pode ser zero.")
            return

        # O arquivo esperado tem somente uma coluna, separada por ponto e vírgula.
        dados_brutos = pd.read_csv(
            arquivo_path,
            header=None,
            names=["saida"],
            dtype=str,
            sep=";",
        )

        if dados_brutos.shape[1] != 1:
            messagebox.showerror(
                "Erro",
                f"O arquivo deve conter apenas 1 coluna.\n"
                f"Foram encontradas {dados_brutos.shape[1]} colunas.",
            )
            return

        # Limpa os valores do CSV e transforma tudo em número.
        # Linhas vazias ou inválidas são descartadas.
        dados_brutos["saida"] = dados_brutos["saida"].map(
            lambda x: str(x).strip().replace(",", ".")
        )
        dados_brutos["saida"] = pd.to_numeric(
            dados_brutos["saida"], errors="coerce"
        )
        dados_brutos = dados_brutos.dropna(subset=["saida"])

        if dados_brutos.empty:
            messagebox.showerror("Erro", "O arquivo CSV está vazio ou inválido.")
            return

        # Monta o vetor de tempo a partir do período de amostragem informado.
        dados = pd.DataFrame()
        dados["saida"] = dados_brutos["saida"].astype(float)
        dados["tempo"] = [i * ts for i in range(len(dados))]

        label_status_valor.config(
            text=(
                f"Dados carregados com sucesso | {len(dados)} amostras | "
                f"1 coluna | Ts = {ts} s"
            )
        )

        plotar_dados_amostrados()

    except ValueError:
        messagebox.showerror(
            "Erro", "Digite valores numéricos válidos para Ts e degrau."
        )
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível carregar o arquivo.\n{e}")


def estimar_parametros():
    global degrau, K_estimado, L_estimado, T_estimado

    try:
        if dados is None or dados.empty:
            messagebox.showerror(
                "Erro", "Carregue os dados antes de estimar os parâmetros."
            )
            return

        t = dados["tempo"].values
        y = dados["saida"].values

        degrau = float(entry_degrau.get().strip().replace(",", "."))

        if degrau == 0:
            messagebox.showerror("Erro", "A amplitude do degrau não pode ser zero.")
            return

        # Chutes iniciais para ajudar o ajuste numérico a convergir.
        K0 = max(float(np.max(y) / degrau), 1e-6)
        L0 = max(float(t[1]) if len(t) > 1 else 0.1, 0.0)
        T0 = max(float(t[-1] / 4), 0.1)

        def modelo_para_ajuste(t, K, L, T):
            return modelo_fopdt(t, K, L, T, degrau)

        # Ajusta K, L e T procurando o modelo que mais se aproxima dos dados medidos.
        parametros, _ = curve_fit(
            modelo_para_ajuste,
            t,
            y,
            p0=[K0, L0, T0],
            bounds=([0, 0, 1e-6], [np.inf, np.inf, np.inf]),
            maxfev=20000,
        )

        K_estimado, L_estimado, T_estimado = parametros

        if K_estimado <= 0 or L_estimado <= 0 or T_estimado <= 0:
            messagebox.showerror("Erro", "Os parâmetros estimados não são válidos.")
            return

        label_k.config(text=f"{K_estimado:.6g}")
        label_l.config(text=f"{L_estimado:.6g} s")
        label_t.config(text=f"{T_estimado:.6g} s")

        # Com K, L e T estimados, aplicamos diretamente as fórmulas clássicas
        # de Ziegler-Nichols em malha aberta para P, PI e PID.
        kp_p = T_estimado / (K_estimado * L_estimado)

        kp_pi = 0.9 * T_estimado / (K_estimado * L_estimado)
        ti_pi = 3.33 * L_estimado

        kp_pid = 1.2 * T_estimado / (K_estimado * L_estimado)
        ti_pid = 2.0 * L_estimado
        td_pid = 0.5 * L_estimado

        texto_parametros = (
            f"P:    Kp = {kp_p:.6g}"
            f"\nPI:   Kp = {kp_pi:.6g} | Ti = {ti_pi:.6g} s"
            f"\nPID:  Kp = {kp_pid:.6g} | Ti = {ti_pid:.6g} s | Td = {td_pid:.6g} s"
        )
        label_parametros.config(text=texto_parametros)

        # Deixa os controladores já escritos no formato usado no MATLAB.
        comando_p = f"Gcp = {kp_p:.6g};"
        comando_pi = (
            f"Gcpi = {kp_pi:.6g} * (1 + 1/({ti_pi:.6g}*tf('s')));"
        )
        comando_pid = (
            f"Gcpid = {kp_pid:.6g} * (1 + 1/({ti_pid:.6g}*tf('s')) + "
            f"{td_pid:.6g}*tf('s'));"
        )

        entry_matlab_p.config(state="normal")
        entry_matlab_p.delete(0, tk.END)
        entry_matlab_p.insert(0, comando_p)
        entry_matlab_p.config(state="readonly")

        entry_matlab_pi.config(state="normal")
        entry_matlab_pi.delete(0, tk.END)
        entry_matlab_pi.insert(0, comando_pi)
        entry_matlab_pi.config(state="readonly")

        entry_matlab_pid.config(state="normal")
        entry_matlab_pid.delete(0, tk.END)
        entry_matlab_pid.insert(0, comando_pid)
        entry_matlab_pid.config(state="readonly")

        plotar_comparacao()
        messagebox.showinfo("Sucesso", "Parâmetros estimados com sucesso.")

    except ValueError:
        messagebox.showerror(
            "Erro",
            "Digite um valor numérico válido para a amplitude do degrau.",
        )
    except Exception as e:
        messagebox.showerror(
            "Erro", f"Não foi possível estimar os parâmetros.\n{e}"
        )


def configurar_eixos(ax, x, y1, y2=None, t_ass=None):
    # Centraliza aqui os ajustes visuais usados nos dois gráficos.
    y_total = np.array(y1, dtype=float)

    if y2 is not None:
        y_total = np.concatenate([y_total, np.array(y2, dtype=float)])

    y_min = float(np.min(y_total))
    y_max = float(np.max(y_total))

    # Dá uma folga no eixo Y para a curva não ficar encostada nas bordas.
    if abs(y_max - y_min) < 1e-12:
        margem_y = max(abs(y_max) * 0.1, 0.1)
    else:
        margem_y = 0.1 * (y_max - y_min)

    ax.set_ylim(y_min - margem_y, y_max + margem_y)

    # Quando existe uma estimativa de acomodação, não precisamos mostrar
    # uma janela de tempo muito maior do que o trecho útil da resposta.
    if t_ass is not None:
        x_max = min(float(np.max(x)), float(t_ass + 2.0))
    else:
        x_max = float(np.max(x))

    if x_max <= 0:
        x_max = 1.0

    ax.set_xlim(0, x_max)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=8))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8))

    fmt = ScalarFormatter(useMathText=True)
    fmt.set_scientific(True)
    fmt.set_powerlimits((-3, 4))
    ax.yaxis.set_major_formatter(fmt)

    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_xlabel("Tempo (s)")
    ax.set_ylabel("Saída")


def desenhar_figura(fig):
    global canvas_grafico

    # Remove o gráfico anterior antes de colocar o novo no mesmo espaço.
    if canvas_grafico is not None:
        canvas_grafico.get_tk_widget().destroy()

    canvas_grafico = FigureCanvasTkAgg(fig, master=frame_grafico)
    canvas_grafico.draw()
    canvas_grafico.get_tk_widget().pack(fill="both", expand=True)
    plt.close(fig)


def plotar_dados_amostrados():
    # Mostra os pontos exatamente como foram lidos do arquivo.
    if dados is None or dados.empty:
        return

    t = dados["tempo"].values
    y = dados["saida"].values

    fig, ax = plt.subplots(figsize=(7, 4), dpi=100)
    ax.plot(
        t,
        y,
        marker="o",
        linestyle="-",
        markersize=3,
        linewidth=1.5,
        label="Dados amostrados",
    )

    configurar_eixos(ax, t, y)
    ax.set_title("Resposta Amostrada da Planta")
    ax.legend()
    fig.tight_layout()
    desenhar_figura(fig)


def plotar_comparacao():
    # Coloca os dados reais e o modelo estimado no mesmo gráfico
    # para conferir visualmente se o ajuste ficou coerente.
    if dados is None or dados.empty:
        return

    if K_estimado is None or L_estimado is None or T_estimado is None:
        return

    t_dados = dados["tempo"].values
    y_real = dados["saida"].values

    # Em um sistema de primeira ordem, L + 4T já representa praticamente
    # toda a região de acomodação da resposta.
    t_ass = L_estimado + 4.0 * T_estimado
    t_final = min(float(np.max(t_dados)), float(t_ass + 2.0))

    t_modelo = np.linspace(0, t_final, 1000)
    y_modelo = modelo_fopdt(
        t_modelo, K_estimado, L_estimado, T_estimado, degrau
    )

    fig, ax = plt.subplots(figsize=(7, 4), dpi=100)
    ax.plot(
        t_dados,
        y_real,
        marker="o",
        linestyle="",
        markersize=3,
        label="Dados amostrados",
    )
    ax.plot(t_modelo, y_modelo, linewidth=2.0, label="Modelo ajustado")

    configurar_eixos(ax, t_modelo, y_modelo, y_real, t_ass=t_ass)
    ax.set_title("Comparação: Dados Amostrados x Modelo Ajustado")
    ax.legend()
    fig.tight_layout()
    desenhar_figura(fig)


# Funções pequenas usadas só para deixar a interface rolável e confortável.
def atualizar_scrollregion(event=None):
    canvas_principal.configure(scrollregion=canvas_principal.bbox("all"))


def ajustar_largura_frame(event):
    canvas_principal.itemconfig(canvas_window, width=event.width)


def rolar_mouse_windows(event):
    canvas_principal.yview_scroll(int(-1 * (event.delta / 120)), "units")


def rolar_mouse_linux_cima(event):
    canvas_principal.yview_scroll(-1, "units")


def rolar_mouse_linux_baixo(event):
    canvas_principal.yview_scroll(1, "units")


def selecionar_tudo_entry(event):
    event.widget.after(1, lambda: event.widget.select_range(0, tk.END))


# Montagem da interface gráfica.
janela = tk.Tk()
janela.title("ZN_Controller")
janela.state("zoomed")

# A tela inteira fica dentro de um canvas para permitir rolagem vertical
# quando a janela não tiver espaço para mostrar tudo de uma vez.
canvas_principal = tk.Canvas(janela)
scrollbar_vertical = tk.Scrollbar(
    janela,
    orient="vertical",
    command=canvas_principal.yview,
)
canvas_principal.configure(yscrollcommand=scrollbar_vertical.set)

scrollbar_vertical.pack(side="right", fill="y")
canvas_principal.pack(side="left", fill="both", expand=True)

frame_principal = tk.Frame(canvas_principal)
canvas_window = canvas_principal.create_window(
    (0, 0), window=frame_principal, anchor="nw"
)

frame_principal.bind("<Configure>", atualizar_scrollregion)
canvas_principal.bind("<Configure>", ajustar_largura_frame)
canvas_principal.bind_all("<MouseWheel>", rolar_mouse_windows)
canvas_principal.bind_all("<Button-4>", rolar_mouse_linux_cima)
canvas_principal.bind_all("<Button-5>", rolar_mouse_linux_baixo)

# Título principal da aplicação.
titulo = tk.Label(
    frame_principal,
    text="Programa para Cálculo dos Parâmetros Ziegler-Nichols em Malha Aberta",
    font=("Arial", 14, "bold"),
)
titulo.pack(pady=10)

frame_superior = tk.Frame(frame_principal)
frame_superior.pack(fill="both", expand=True, padx=15, pady=10)

frame_esquerda = tk.Frame(frame_superior)
frame_esquerda.pack(side="left", fill="y", padx=10)

# Área onde o usuário escolhe o arquivo e informa Ts e a amplitude do degrau.
frame_entrada = tk.LabelFrame(
    frame_esquerda,
    text="Entrada de Dados",
    padx=10,
    pady=10,
)
frame_entrada.pack(fill="x", pady=10)

btn_arquivo = tk.Button(
    frame_entrada,
    text="Selecionar CSV",
    command=selecionar_arquivo,
    width=20,
)
btn_arquivo.grid(row=0, column=0, padx=5, pady=5)

tk.Label(frame_entrada, text="Arquivo selecionado:").grid(
    row=1, column=0, sticky="w", padx=5, pady=5
)

label_arquivo_valor = tk.Label(
    frame_entrada,
    text="Nenhum arquivo selecionado",
    anchor="w",
    wraplength=300,
    justify="left",
)
label_arquivo_valor.grid(row=1, column=1, sticky="w", padx=5, pady=5)

tk.Label(frame_entrada, text="Tempo de amostragem Ts (s):").grid(
    row=2, column=0, sticky="w", padx=5, pady=5
)
entry_ts = tk.Entry(frame_entrada, width=15)
entry_ts.grid(row=2, column=1, sticky="w", padx=5, pady=5)
entry_ts.insert(0, "0.1")

tk.Label(frame_entrada, text="Amplitude do degrau:").grid(
    row=3, column=0, sticky="w", padx=5, pady=5
)
entry_degrau = tk.Entry(frame_entrada, width=15)
entry_degrau.grid(row=3, column=1, sticky="w", padx=5, pady=5)
entry_degrau.insert(0, "1.0")

btn_carregar = tk.Button(
    frame_entrada,
    text="Carregar Dados",
    command=carregar_dados,
    width=20,
)
btn_carregar.grid(row=4, column=0, padx=5, pady=10)

btn_estimativa = tk.Button(
    frame_entrada,
    text="Estimar Parâmetros",
    command=estimar_parametros,
    width=20,
)
btn_estimativa.grid(row=4, column=1, padx=5, pady=10)

tk.Label(frame_entrada, text="Status:").grid(
    row=5, column=0, sticky="w", padx=5, pady=5
)
label_status_valor = tk.Label(
    frame_entrada,
    text="Aguardando carregamento dos dados...",
    anchor="w",
    wraplength=300,
    justify="left",
)
label_status_valor.grid(row=5, column=1, sticky="w", padx=5, pady=5)

# Área de resultados: parâmetros da planta, sintonia e comandos do MATLAB.
frame_resultados = tk.LabelFrame(
    frame_esquerda,
    text="Resultados",
    padx=10,
    pady=10,
)
frame_resultados.pack(fill="both", expand=True, pady=10)

tk.Label(
    frame_resultados,
    text="Parâmetros da planta:",
    font=("Arial", 11, "bold"),
).grid(row=0, column=0, sticky="w", pady=(5, 10))

tk.Label(frame_resultados, text="Ganho do processo (K):").grid(
    row=1, column=0, sticky="w", padx=5, pady=5
)
label_k = tk.Label(frame_resultados, text="---")
label_k.grid(row=1, column=1, sticky="w", padx=5, pady=5)

tk.Label(frame_resultados, text="Atraso (L):").grid(
    row=2, column=0, sticky="w", padx=5, pady=5
)
label_l = tk.Label(frame_resultados, text="---")
label_l.grid(row=2, column=1, sticky="w", padx=5, pady=5)

tk.Label(frame_resultados, text="Constante de tempo (T):").grid(
    row=3, column=0, sticky="w", padx=5, pady=5
)
label_t = tk.Label(frame_resultados, text="---")
label_t.grid(row=3, column=1, sticky="w", padx=5, pady=5)

tk.Label(
    frame_resultados,
    text="Controladores:",
    font=("Arial", 11, "bold"),
).grid(row=4, column=0, sticky="w", pady=(20, 10))

label_parametros = tk.Label(
    frame_resultados,
    text="---",
    justify="left",
    anchor="w",
    wraplength=320,
    font=("Arial", 10),
)
label_parametros.grid(
    row=5,
    column=0,
    columnspan=2,
    sticky="w",
    padx=5,
    pady=5,
)

tk.Label(
    frame_resultados,
    text="Comandos MATLAB:",
    font=("Arial", 11, "bold"),
).grid(row=7, column=0, sticky="w", pady=(20, 10))

tk.Label(frame_resultados, text="Gcp =").grid(
    row=8, column=0, sticky="w", padx=5, pady=5
)
entry_matlab_p = tk.Entry(frame_resultados, width=55)
entry_matlab_p.grid(row=8, column=1, sticky="w", padx=5, pady=5)

tk.Label(frame_resultados, text="Gcpi =").grid(
    row=9, column=0, sticky="w", padx=5, pady=5
)
entry_matlab_pi = tk.Entry(frame_resultados, width=55)
entry_matlab_pi.grid(row=9, column=1, sticky="w", padx=5, pady=5)

tk.Label(frame_resultados, text="Gcpid =").grid(
    row=10, column=0, sticky="w", padx=5, pady=5
)
entry_matlab_pid = tk.Entry(frame_resultados, width=55)
entry_matlab_pid.grid(row=10, column=1, sticky="w", padx=5, pady=5)

entry_matlab_p.config(state="readonly")
entry_matlab_pi.config(state="readonly")
entry_matlab_pid.config(state="readonly")

entry_matlab_p.bind("<Button-1>", selecionar_tudo_entry)
entry_matlab_pi.bind("<Button-1>", selecionar_tudo_entry)
entry_matlab_pid.bind("<Button-1>", selecionar_tudo_entry)

# O gráfico ocupa a parte direita da janela.
frame_grafico = tk.LabelFrame(
    frame_superior,
    text="Gráfico",
    padx=10,
    pady=10,
)
frame_grafico.pack(
    side="right",
    fill="both",
    expand=True,
    padx=10,
    pady=10,
)

# Mantém a janela aberta e processando os eventos dos botões.
janela.mainloop()
