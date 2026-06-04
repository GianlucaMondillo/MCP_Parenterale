# Parenterale MCP Server

MCP server per il calcolo della nutrizione parenterale neonatale, progettato per l'uso con Claude Desktop.

## Demo

https://github.com/user-attachments/assets/demo.mp4

## Funzionalita

- **Calcolo completo sacca PN** classica (glucosio, aminoacidi, lipidi, elettroliti)
- **Supporto Numeta G13E** (300 ml con lipidi / 240 ml senza lipidi)
- **25+ latti e formule** con composizione nutrizionale completa
- **Fabbisogni raccomandati** per peso e giorno di vita (linee guida)
- **Fabbisogno idrico** automatico da tabelle IDRICO
- **Calcolo osmolarita** finale della sacca
- **Controlli di sicurezza**: rapporto Ca:P, accesso venoso periferico/centrale
- **Badge colorati** (verde/giallo/rosso) per confronto con fabbisogno raccomandato
- **Scheda farmacia** pronta per la stampa
- **Vitamine e oligoelementi** (Vitalipid, Soluvit, Peditrace)
- **Due modalita**: per volumi o per apporti/kg
- **Sottrazione automatica** del contributo del latte dai target PN

## Installazione

### Requisiti

- Python >= 3.10
- pip

### Installa dipendenze

```bash
pip install mcp
```

### Configura Claude Desktop

Modifica il file `claude_desktop_config.json`:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Aggiungi:

```json
{
  "mcpServers": {
    "parenterale": {
      "command": "python",
      "args": ["/percorso/assoluto/a/parenterale_mcp_server.py"]
    }
  }
}
```

Se hai piu versioni di Python, specifica il percorso completo dell'eseguibile Python 3.10+:

```json
{
  "mcpServers": {
    "parenterale": {
      "command": "C:\\Users\\tuoutente\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",
      "args": ["C:\\Users\\tuoutente\\Documents\\parenterale-mcp-server\\parenterale_mcp_server.py"]
    }
  }
}
```

Riavvia Claude Desktop dopo la modifica.

## Tool disponibili

| Tool | Descrizione |
|------|-------------|
| `list_formulas` | Elenca tutti i latti/formule disponibili con composizione per 100ml |
| `list_solutions` | Elenca le soluzioni PN con concentrazione e osmolarita |
| `get_requirements` | Fabbisogni raccomandati dato peso e giorno di vita |
| `get_vitamin_dosages` | Dosaggi vitamine/oligoelementi per peso |
| `calculate_pn` | Calcolo completo della sacca PN |

## Esempi d'uso

Su Claude Desktop, puoi chiedere:

> "Calcola una parenterale per un neonato di 1.8 kg, giorno di vita 3, eta gestazionale 30+4"

> "Calcola la sacca PN: peso 1.2 kg, giorno 2, glucosio 6 g/kg con soluzione al 33%, proteine 1.5 g/kg, lipidi 2.5 g/kg con Intralipid 20%"

> "Calcola una parenterale con Numeta G13E 300 ml per un neonato di 1.5 kg, giorno 5"

> "Calcola la sacca PN per un neonato di 2.5 kg, giorno 3, che prende 80 ml/die di Aptamil 1"

## Output

Il tool `calculate_pn` restituisce:

- **macros**: proteine, glucosio, lipidi, kcal (PN, latte, totale) con confronto fabbisogno
- **electrolytes**: Na, K, Ca, P, Mg, Cl (PN, latte, totale) con confronto fabbisogno
- **volumes**: soluzioni, acqua bidistillata, sacca netta, deflussore, velocita infusione
- **safety**: osmolarita/accesso venoso, rapporto Ca:P, consiglio diluizione Numeta
- **pharmacy_print**: scheda farmacia in testo pronto da stampare

## Modalita di lavoro

- **apporti** (default): inserisci i target per kg (g/kg, mEq/kg, mg/kg), il server calcola i volumi delle soluzioni
- **vol**: inserisci i volumi (ml), il server calcola gli apporti per kg

In modalita apporti, il contributo del latte viene sottratto automaticamente dai target.

## Licenza

MIT
