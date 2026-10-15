import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import os


# Variáveis que guardam o estado atual da aplicação.
# Como a interface é simples, elas ficam compartilhadas entre os botões e os gráficos.
arquivo_path = ""
dados = None
canvas_grafico = None
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
