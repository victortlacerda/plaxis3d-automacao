#!/usr/bin/env bash
# Regressão por mock (sem PLAXIS). Compara o log de comandos / a saída dos scripts com tests/baselines/.
#   ./tests/regressao.sh            -> confere (retorna erro se algo mudou)
#   ./tests/regressao.sh --gravar   -> grava/atualiza as linhas de base (só depois de revisar a mudança!)
set -u
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
T="$RAIZ/tests"
GRAVAR=0; [ "${1:-}" = "--gravar" ] && GRAVAR=1
FALHAS=0
FILTRO='^(>>>|   (CALL|SET|SETITEM|\[))|^    \(|^    -'

normaliza() { sed "s#$1#<DIR>#g"; }

compara() {  # nome  arquivo_novo
  local base="$T/baselines/$1"
  if [ $GRAVAR -eq 1 ]; then cp "$2" "$base"; echo "gravado: $1"; return; fi
  if diff -q "$base" "$2" >/dev/null 2>&1; then echo "OK        $1"; else echo "DIFERE    $1"; diff "$base" "$2" | head -20; FALHAS=$((FALHAS+1)); fi
}

interativo() {  # nome  script  entradas
  local d; d="$(mktemp -d)"
  ( cd "$d" && python3 "$T/mock/rodar_interativo.py" "$RAIZ/$2" < "$T/entradas/$3" 2>&1 \
      | grep -E "$FILTRO" | grep -v "g_i.echo()" | normaliza "$d" > "$d/saida.log" )
  compara "$1.log" "$d/saida.log"; rm -rf "$d"
}

resultados() {  # nome  script  fake  json
  local d; d="$(mktemp -d)"
  ( cd "$d" && python3 "$T/mock/rodar_resultados.py" "$RAIZ/$2" "$3" "$T/dados/$4" 2>&1 | normaliza "$d" > "$d/saida.log"
    [ -f sapata_curva.csv ] && cat sapata_curva.csv >> "$d/saida.log"
    [ -f sapata_peso_proprio.csv ] && cat sapata_peso_proprio.csv >> "$d/saida.log"
    [ -f subsolo_piso.csv ] && cat subsolo_piso.csv >> "$d/saida.log" )
  compara "$1.log" "$d/saida.log"; rm -rf "$d"
}

soiltest() {  # nome  script  modelo  drenagem  json_config
  local d; d="$(mktemp -d)"
  ( cd "$d" && python3 "$T/mock/rodar_soiltest.py" "$RAIZ/$2" "$3" "$4" "$5" 2>&1 \
      | normaliza "$d" | sed -E 's/\(20[0-9]{2}-[0-9-]+T[0-9:]+\)/(<DATA>)/; s/_20[0-9]{6}_[0-9]{6}/_<DATA>/g; s/ at 0x[0-9a-f]+/ at 0x<END>/g' > "$d/saida.log" )
  compara "$1.log" "$d/saida.log"; rm -rf "$d"
}

ferramenta() {  # nome  script(em soiltest/)  [MODELO:DREN:nome ...]  (materiais ja existentes no projeto)
  local d n="$1" sc="$2"; shift 2; d="$(mktemp -d)"
  cp "$RAIZ/soiltest/plaxis_soiltest_auto.py" "$RAIZ/soiltest/$sc" "$RAIZ/soiltest/materiais_modelo.csv" "$d/"
  ( cd "$d" && python3 "$T/mock/rodar_ferramenta.py" "$d/$sc" "$@" 2>&1 \
      | normaliza "$d" | sed -E 's/\(20[0-9]{2}-[0-9-]+T[0-9:]+\)/(<DATA>)/; s/_20[0-9]{6}_[0-9]{6}/_<DATA>/g; s/ at 0x[0-9a-f]+/ at 0x<END>/g' > "$d/saida.log"
    cat "$d"/soiltest_saida/*/log.txt 2>/dev/null | normaliza "$d" | sed -E 's/\(20[0-9]{2}-[0-9-]+T[0-9:]+\)/(<DATA>)/; s/_20[0-9]{6}_[0-9]{6}/_<DATA>/g; s/ at 0x[0-9a-f]+/ at 0x<END>/g' >> "$d/saida.log"
    ls "$d"/soiltest_saida/*/relatorio.html >/dev/null 2>&1 && echo "relatorio.html gerado" >> "$d/saida.log" )
  compara "$n.log" "$d/saida.log"; rm -rf "$d"
}

# --- sapata (ESTÁVEL): módulos 1, 2, 3 (sequência e simultâneo) + opções novas
interativo sapata_int_carga sapata/plaxis_sapata_interativo.py sapata_carga.txt
interativo sapata_int_desl sapata/plaxis_sapata_interativo.py sapata_desl.txt
interativo sapata_int_seq sapata/plaxis_sapata_interativo.py sapata_seq.txt
interativo sapata_int_sim sapata/plaxis_sapata_interativo.py sapata_sim.txt
interativo sapata_int_volume_sem_acao sapata/plaxis_sapata_interativo.py sapata_volume_sem_acao.txt
interativo sapata_int_duas_cargas sapata/plaxis_sapata_interativo.py sapata_duas_cargas.txt
for m in carga desl seq sim duas_cargas sem_acao; do
  resultados sapata_res_$m sapata/plaxis_sapata_resultados.py sapata_resultados sapata_$m.json
done
# --- subsolo (EM DESENVOLVIMENTO)
interativo subsolo_int_padrao subsolo/plaxis_subsolo_interativo.py subsolo_padrao.txt
resultados subsolo_res_padrao subsolo/plaxis_subsolo_resultados.py subsolo_resultados subsolo.json

# --- soiltest: versao estavel (mesmo fluxo das rodadas reais) e versao em desenvolvimento
soiltest soiltest_le_todos soiltest/plaxis_soiltest_auto.py LE D '{"crs":{"rodar":true},"dss":{"rodar":true,"pressoes_kPa":[50]},"cdss":{"rodar":true},"triaxial_ciclico":{"rodar":true},"triaxial":{"pressoes_kPa":[50]}}'
soiltest soiltest_hs_k0_ocr soiltest/plaxis_soiltest_auto.py HS D '{"consolidacao":{"tipo":"K0","K0":0.5},"preadensamento":{"modo":"OCR","valor":2},"dilatancy_cutoff":{"ligar":true},"oedometer":{"rodar":false}}'
soiltest soiltest_estavel_ciclico_tensao soiltest/plaxis_soiltest_auto.py MC D '{"triaxial":{"rodar":false},"oedometer":{"rodar":false},"cdss":{"rodar":true,"comportamentos":["Undrained"],"controle":"Stress","amplitude":20}}'
soiltest soiltest_dev_ciclico_nao_drenado soiltest/em_desenvolvimento/plaxis_soiltest_auto_dev.py MC D '{"triaxial":{"rodar":false},"oedometer":{"rodar":false},"cdss":{"rodar":true,"comportamentos":["Undrained"],"controle":"Stress","amplitude":20},"triaxial_ciclico":{"rodar":true,"comportamentos":["Undrained"]}}'

# --- soiltest: ferramentas (parametrico, G/G0, biblioteca, auditoria)
ferramenta ferr_parametrico soiltest_parametrico.py
ferramenta ferr_gg0 soiltest_gg0.py
ferramenta ferr_biblioteca soiltest_biblioteca.py
ferramenta ferr_auditoria soiltest_auditoria.py 2:0:Aterro 8:0:Argila 5:2:Errada

# --- estudos (lote, analítico, painel do resumo)
estudo_lote() {
  local d; d="$(mktemp -d)"
  ( cd "$d" && printf "%s\ns\n" "$RAIZ/estudos/sapatas_lote.xlsx" | python3 "$T/mock/rodar_estudo.py" "$RAIZ/estudos/sapata_lote.py" >/dev/null 2>&1
    cut -d";" -f1-17,19 lote_*/resumo_lote.csv > "$d/saida.log"
    for c in lote_*/*/; do ls "$c" >> "$d/saida.log"; done )
  compara "estudos_lote.log" "$d/saida.log"; rm -rf "$d"
}
estudo_lote
if python3 "$RAIZ/estudos/sapata_analitico.py" > /dev/null; then echo "OK        analitico (valores de livro)"; else echo "DIFERE    analitico"; FALHAS=$((FALHAS+1)); fi

[ $GRAVAR -eq 1 ] && exit 0
[ $FALHAS -eq 0 ] && echo "Tudo igual às linhas de base." || { echo "$FALHAS caso(s) mudaram."; exit 1; }
