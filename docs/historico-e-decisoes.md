# Histórico e decisões

- **Execução:** executor externo com `s_i/g_i` prontos; sem pergunta de porta (só sem o executor).
- **Módulos independentes** (`modo`: carga | deslocamento | combinado | nenhuma) para nunca quebrar o validado.
- **Curva por deslocamento prescrito:** força por passo em `Reached.Force*`, conferida contra a reação no último passo.
- **Subsolo (Caso B):** script separado, tolerante a falhas (`seguro()`), para evoluir sem tocar na sapata.
- **Mock:** cada mudança em `sapata/` passa por `tests/regressao.sh`; o mock não valida nomes reais de propriedades.
- **Pendente:** ver `subsolo/README.md`. O histórico de comandos do Caso B feito na interface do PLAXIS é a próxima entrada.
- **Observação sobre o histórico do Git:** o código vinha sendo gerado sem controle de versão; os commits aqui
  organizam o estado atual por componente (não reproduzem as iterações anteriores). A partir daqui o histórico é real.
