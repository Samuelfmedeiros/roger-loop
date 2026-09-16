# Roger Loop — o orquestrador de test-loop config-driven

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-6366f1?style=flat-square" alt="Licença"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/depend%C3%AAncias-0-22c55e?style=flat-square" alt="Zero dependências">
  <img src="https://img.shields.io/badge/providers-qualquer-0ea5e9?style=flat-square" alt="Agnóstico de provedor">
  <img src="https://github.com/Samuelfmedeiros/roger-loop/actions/workflows/tests.yml/badge.svg" alt="CI">
</p>

<p align="center"><strong>Roda seu ciclo crítico → builder → revisor com orçamentos rígidos e zero confiança na própria memória</strong> — um arquivo JSON configura tudo, qualquer agente de linha de comando se encaixa, e nenhum provedor de modelo é embutido.</p>

> 🌐 [English](README.md) · **Português**

Test-loops agênticos falham de um jeito que parece sucesso. O crítico morreu e a rodada tirou 0, que o loop lê como "defeito de código"; o state de ontem responde a campanha de hoje com 100/100 que nunca foi computado; um gap fechado na rodada 3 reabre na 5 e o loop converge mesmo assim; um LLM avaliando o próprio argumento deriva para o acordo. Nada disso quebra. Tudo isso vai pra produção.

**O Roger Loop é o motor que esses incidentes construíram.** Ele orquestra qualquer crítico determinístico, qualquer builder e qualquer revisor como comandos stdin/stdout, e cada piece de memória que guarda carrega prova de onde veio.

## O que ele garante

| Risco em loops ingênuos | Guarda aqui | Módulo |
|---|---|---|
| Saída do crítico quebra → `0` silencioso lido como defeito | Parser devolve `None` + inconclusiva; rodada de ambiente nunca pontua | `rogerloop/verdict.py` |
| State sobrevive à campanha → nota herdada | Fingerprint = git HEAD do `campaign_path` + hash do comando do crítico; divergiu, o state é arquivado e a rodada 1 roda de verdade | `rogerloop/state.py` |
| Diretório não-git → fingerprint `None` → brecha de resume | Fingerprint `None` **proíbe** resume | `rogerloop/state.py` |
| Gap flap fecha → abre, loop "converge" | Histórico de gaps fechados; reabertura carimba `REGRESSAO:` no log | `rogerloop/state.py` |
| Nota na zona cinzenta: aceitar ou gastar rodada? | Duas visões isoladas (pró/contra, contexto fresco) + juiz; perna morta ⇒ falha para o trabalho, nunca para o falso verde | `rogerloop/debate.py` |
| Saída de builder/crítico injetada no próximo prompt | `quarantine()` cerca texto não-confiável como dado, remove controle e cercas forjadas | `rogerloop/verdict.py` |
| Loop roda para sempre | `max_rounds` + `max_minutes` de parede, honrados | `rogerloop/engine.py` |

## O contrato

O crítico deve imprimir, em qualquer ordem, no stdout:

```
SCORE=<0-100>
GAPS=<gap a|gap b>
DETAIL=<uma linha>
```

Builder / revisor / pernas do debate são **qualquer comando** que lê um
prompt no stdin e escreve texto no stdout — um CLI agent, `curl` para um
modelo local, um shell script. Aqui ninguém sabe de provedores, APIs ou
contas.

## Começando

```bash
git clone https://github.com/Samuelfmedeiros/roger-loop && cd roger-loop
python3 -m rogerloop --selftest          # contrato, guards de estado, e2e, orçamentos

cp examples/loop.json meu-loop.json      # aponte path/critic/builder para o seu mundo
python3 -m rogerloop --config meu-loop.json
# STATUS=converged SCORE=100 ROUNDS=2 GAPS=- CAVEATS=- WALL=41s
```

Exit code `0` só quando converge; estado e log com timestamp vivem em
`$ROGERLOOP_STATE` (padrão `~/.rogerloop`), um arquivo por nome de campanha —
nunca compartilhado.

## Anatomia de uma rodada

```
 critico (deterministico, saida cercada)
   score >= gate            -> assinatura do revisor (se houver) -> CONVERGEOU
   gray_low <= score < gate -> debate:  pro | con -> juiz
                                PASS / PASS_WITH_CAVEATS -> CONVERGEOU
                                REPROVO / INCONCLUSIVO   -> rodada do builder
   score < gate             -> rodada do builder (gaps roteados por classe)
   score = None             -> strike de ambiente; 2 strikes -> AMBIENTE_QUEBRADO
```

## Por que existe (e de onde veio)

Este motor é o núcleo generalizado de um test-loop que roda entregas reais
em muitos projetos desde meados de 2025 — incluindo a manutenção dele
mesmo: cada guarda da tabela acima existe porque o incidente dela aconteceu
uma vez, foi diagnosticado de log e virou teste unitário. É o irmão do
[roger-mlops](https://github.com/Samuelfmedeiros/roger-mlops), que cobre o
lado de runtime de treino longo de GPU; os dois compartilham o contrato
`SCORE=/GAPS=/DETAIL=` e nenhum dos dois sabe que modelo você usa.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Cobrem: parser (clamp, contrato ausente, `0 passed`), arquivamento de nota
herdada por mudança de fingerprint e de fonte do crítico, banimento de
resume não-git, regressão de gap flap, forja de cerca, finais de campanha
converge/orçamento/ambiente, e validação de config.

## Licença

MIT — veja [LICENSE](LICENSE).
