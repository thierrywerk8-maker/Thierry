#!/usr/bin/env python3
"""Bouwt de opgeschoonde SMB-leaddatabase.

Invoer:
  --smb        Small_to_medium_Business(Paylogic fit).csv  (cp1252, komma)
  --gescreend  SMB_leads_gescreend.csv                     (cp1252, puntkomma, kolom Screening)
  --zoho       Zoho-export Leads_<datum>.xlsx
  --regels     screening_regels.csv                        (utf-8, puntkomma)
Uitvoer:
  --out        xlsx met tabbladen SMB database, Uitgesloten, Samenvatting, Bronnen

Werkwijze:
  1. Leads die de collega verwijderde of die een regel met actie "Verwijderen" raken,
     gaan naar Uitgesloten. Dit geldt voor beide bronnen.
  2. Leads die de collega als "Te controleren" markeerde, of die een regel met actie
     "Te controleren" raken, blijven staan met Screening = "Te controleren".
  3. Zoho-leads worden op genormaliseerde bedrijfsnaam aan SMB-rijen gekoppeld.
     Zoho is leidend voor tickets, status en ticketsolution.
"""
import argparse
import collections
import csv
import io
import re
import unicodedata
import warnings

import openpyxl
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

HEADERS = ["Company", "Name Event", "Midcase Tickets P/Y", "Lead Vertical",
           "Ticketsolution", "System", "Lead Status", "Totaal aantal tickets"]
TE_CONTROLEREN = "Te controleren"
SPORTBOND = "Landelijke sportbond"
BLAUW = "CFE2F3"
COLLEGA = "Colleguescreening"


# ---------------------------------------------------------------- helpers
def fix_mojibake(s):
    """Herstelt dubbel gecodeerde tekst zoals 'LaMÃ¨re' -> 'LaMère'."""
    def repair(m):
        try:
            return m.group().encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return m.group()
    return re.sub(r"[ÃÂ].", repair, s or "")


def clean(s):
    return fix_mojibake(re.sub(r"\s+", " ", (s or "").strip()))


def plain(s):
    """Kleine letters zonder accenten, voor het zoeken met regels."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def norm_company(s):
    """Sleutel om bedrijfsnamen tussen bronnen te koppelen."""
    s = plain(s)
    s = re.sub(r"\b(b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|stichting|stg|vereniging)(?=\W|$)", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def to_int(v):
    if v is None:
        return None
    s = str(v).strip().replace(".", "").replace(",", "")
    return int(s) if s.isdigit() else None


def read_csv(path, delimiter):
    with open(path, "rb") as f:
        text = f.read().decode("cp1252")
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


# ---------------------------------------------------------------- inlezen
def load_smb(path):
    rows = []
    for r in read_csv(path, ",")[1:]:
        if not any(c.strip() for c in r):
            continue
        rows.append({
            "company": clean(r[0]), "event": clean(r[1]), "tickets": to_int(r[2]),
            "vertical": clean(r[3]), "solution": clean(r[4]), "system": clean(r[5]),
            "status": clean(r[6]), "raw_key": (r[0].strip(), r[1].strip(), r[2].strip()),
        })
    return rows


def load_gescreend(path):
    kept, flagged = collections.Counter(), collections.Counter()
    for r in read_csv(path, ";")[1:]:
        if not any(c.strip() for c in r):
            continue
        key = (r[0].strip(), r[1].strip(), r[2].strip())
        kept[key] += 1
        if r[10].strip() == TE_CONTROLEREN:
            flagged[key] += 1
    return kept, flagged


def load_zoho(path):
    ws = openpyxl.load_workbook(path, read_only=True).active
    it = ws.iter_rows(values_only=True)
    head = [str(h) for h in next(it)]
    ix = {h: i for i, h in enumerate(head)}
    rows = []
    for r in it:
        if not r or not r[ix["Company"]]:
            continue
        rows.append({
            "record_id": r[ix["Record Id"]],
            "company": clean(str(r[ix["Company"]])),
            "tickets": to_int(r[ix["Midcase Online Retail tickets p/y"]]),
            "solution": clean(str(r[ix["Current or last used Ticketsolution"]] or "")),
            "status": clean(str(r[ix["Lead Status"]] or "")),
        })
    return rows


def load_rules(path):
    with open(path, encoding="utf-8-sig") as f:
        rules = list(csv.DictReader(f, delimiter=";"))
    for r in rules:
        r["rx"] = re.compile(r["zoekpatroon"])
    return rules


def match_rule(rules, actie, *texts):
    for rule in rules:
        if rule["actie"] != actie:
            continue
        for t in texts:
            if t and rule["rx"].search(plain(t)):
                return rule
    return None


# ---------------------------------------------------------------- screening en samenvoegen
def build(args):
    smb = load_smb(args.smb)
    kept, flagged = load_gescreend(args.gescreend)
    zoho = load_zoho(args.zoho)
    rules = load_rules(args.regels)
    log = collections.Counter()
    extra = f"Aanvullende screening {args.datum}"

    # 1. Screening van de SMB-rijen
    for r in smb:
        r["excluded"] = None
        r["screening"] = ""
        r["notes"] = []
        in_range = r["tickets"] is not None and 5000 <= r["tickets"] <= 20000
        rem_rule = match_rule(rules, "Verwijderen", r["company"], r["event"])
        if in_range and kept[r["raw_key"]] == 0:
            r["excluded"] = {
                "moeder": rem_rule["moederorganisatie"] if rem_rule else "",
                "reden": rem_rule["reden"] if rem_rule else "Verwijderd in colleguescreening",
                "door": COLLEGA,
                "verificatie": rem_rule["verificatie"] if rem_rule else "",
            }
            log["smb_collega_verwijderd"] += 1
            if not rem_rule:
                log["collega_zonder_regel"] += 1
                print("  LET OP: geen regel voor colleguverwijdering:", r["company"], "|", r["event"])
            continue
        if in_range:
            kept[r["raw_key"]] -= 1
        if rem_rule:
            r["excluded"] = {"moeder": rem_rule["moederorganisatie"], "reden": rem_rule["reden"],
                             "door": extra, "verificatie": rem_rule["verificatie"]}
            log["smb_regel_verwijderd"] += 1
            if in_range:
                print("  LET OP: regel verwijdert lead die collega liet staan:", r["company"], "|", r["event"])
            continue
        if flagged[r["raw_key"]] > 0:
            flagged[r["raw_key"]] -= 1
            r["screening"] = TE_CONTROLEREN
            r["notes"].append("Screening: twijfelgeval uit colleguescreening")
            log["smb_collega_te_controleren"] += 1
            continue
        tc_rule = match_rule(rules, TE_CONTROLEREN, r["company"], r["event"])
        if tc_rule:
            r["screening"] = TE_CONTROLEREN
            r["notes"].append(f"Screening: {tc_rule['reden']}")
            log["smb_regel_te_controleren"] += 1

    # bedrijfsnamen die de screening raakte, ook voor Zoho-leads zonder gekoppelde rij
    excluded_by_company = {norm_company(r["company"]): r["excluded"] for r in smb if r["excluded"]}
    flagged_companies = {norm_company(r["company"]) for r in smb if r["screening"] == TE_CONTROLEREN}

    # 2. Zoho koppelen aan SMB-rijen
    by_company = collections.defaultdict(list)
    for i, r in enumerate(smb):
        by_company[norm_company(r["company"])].append(i)
    paired = {}
    zoho_only = []
    for z in zoho:
        cands = [i for i in by_company.get(norm_company(z["company"]), []) if i not in paired]
        if not cands:
            zoho_only.append(z)
            continue
        same = [i for i in cands if smb[i]["tickets"] == z["tickets"]]
        paired[(same or cands)[0]] = z

    out, excluded = [], []
    seen = {}  # (bedrijf, tickets) -> uitvoerrij, om dubbele Zoho-leads te herkennen

    for i, r in enumerate(smb):
        z = paired.get(i)
        row = {
            "company": r["company"], "event": r["event"], "tickets": r["tickets"],
            "vertical": r["vertical"], "solution": r["solution"], "system": r["system"],
            "status": r["status"], "screening": r["screening"], "bron": "SMB-lijst",
            "notes": list(r["notes"]),
        }
        if z:
            row["bron"] = "Beide"
            if z["tickets"] is not None and z["tickets"] != r["tickets"]:
                row["notes"].append(f"SMB-lijst: {r['tickets']:,} tickets".replace(",", "."))
            if z["tickets"] is not None:
                row["tickets"] = z["tickets"]
            if z["solution"]:
                row["solution"] = z["solution"]
            if z["status"]:
                row["status"] = z["status"]
            seen[(norm_company(z["company"]), z["tickets"])] = row
        if r["excluded"]:
            row.update(r["excluded"])
            excluded.append(row)
            log["zoho_mee_verwijderd"] += 1 if z else 0
        else:
            out.append(row)

    for z in zoho_only:
        key = (norm_company(z["company"]), z["tickets"])
        if key in seen:
            target = seen[key]
            target["dubbel"] = target.get("dubbel", 1) + 1
            log["zoho_dubbel"] += 1
            continue
        row = {"company": z["company"], "event": "", "tickets": z["tickets"], "vertical": "",
               "solution": z["solution"], "system": "", "status": z["status"],
               "screening": "", "bron": "Zoho", "notes": []}
        seen[key] = row
        nc = norm_company(z["company"])
        rem_rule = match_rule(rules, "Verwijderen", z["company"])
        if rem_rule or nc in excluded_by_company:
            ex = ({"moeder": rem_rule["moederorganisatie"], "reden": rem_rule["reden"],
                   "door": extra, "verificatie": rem_rule["verificatie"]}
                  if rem_rule else excluded_by_company[nc])
            row.update(ex)
            excluded.append(row)
            log["zoho_verwijderd"] += 1
            continue
        tc_rule = match_rule(rules, TE_CONTROLEREN, z["company"])
        if nc in flagged_companies:
            row["screening"] = TE_CONTROLEREN
            row["notes"].append("Screening: zelfde bedrijf als twijfelgeval uit colleguescreening")
        elif tc_rule:
            row["screening"] = TE_CONTROLEREN
            row["notes"].append(f"Screening: {tc_rule['reden']}")
        out.append(row)

    for row in out + excluded:
        if row.get("dubbel"):
            row["notes"].append(f"Staat {row['dubbel']}x in Zoho")

    # sorteren zoals de SMB-lijst: oplopend op tickets, ontbrekende aantallen bovenaan
    key = lambda r: (r["tickets"] is not None, r["tickets"] or 0)
    out.sort(key=key)
    excluded.sort(key=key)

    log["smb_in"] = len(smb)
    log["zoho_in"] = len(zoho)
    log["zoho_gekoppeld"] = len(paired)
    log["zoho_alleen"] = len(zoho_only)
    log["uit"] = len(out)
    log["uitgesloten"] = len(excluded)
    return out, excluded, log


# ---------------------------------------------------------------- werkboek
FONT = "Arial"
NAVY = "1F3864"
THIN = Side(style="thin", color="BFBFBF")


def style_header(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = Border(bottom=THIN)
    ws.row_dimensions[1].height = 30


def write_rows(ws, rows, columns):
    for r_i, row in enumerate(rows, start=2):
        for c_i, (_, getter) in enumerate(columns, start=1):
            v = getter(row)
            cell = ws.cell(row=r_i, column=c_i, value=v if v != "" else None)
            cell.font = Font(name=FONT, size=10)


def lead_columns(extra):
    base = [
        ("Company", lambda r: r["company"]),
        ("Name Event", lambda r: r["event"]),
        ("Midcase Tickets P/Y", lambda r: r["tickets"]),
        ("Lead Vertical", lambda r: r["vertical"]),
        ("Ticketsolution", lambda r: r["solution"]),
        ("System", lambda r: r["system"]),
        ("Lead Status", lambda r: r["status"]),
        ("Totaal aantal tickets", lambda r: None),
    ]
    return base + extra


def add_formats(ws, last_row, last_col_letter, red=True, blue=False):
    end = last_row + 1000  # opmaak loopt door voor rijen die later worden toegevoegd
    rng = f"A2:{last_col_letter}{end}"
    if red:
        ws.conditional_formatting.add(
            f"C2:C{end}",
            FormulaRule(formula=['AND($A2<>"",OR($C2="",$C2=0))'],
                        fill=PatternFill("solid", fgColor="E06666", bgColor="E06666"),
                        font=Font(name=FONT, bold=True, color="FFFFFF"), stopIfTrue=True))
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=['AND($A2<>"",OR($C2="",$C2=0))'],
                        fill=PatternFill("solid", fgColor="F4CCCC", bgColor="F4CCCC"), stopIfTrue=True))
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'$I2="{TE_CONTROLEREN}"'],
                        fill=PatternFill("solid", fgColor="FCE5CD", bgColor="FCE5CD"), stopIfTrue=True))
    if blue:
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'$J2="{SPORTBOND}"'],
                        fill=PatternFill("solid", fgColor=BLAUW, bgColor=BLAUW), stopIfTrue=True))
    ws.conditional_formatting.add(
        rng,
        FormulaRule(formula=['AND($A2<>"",MOD(ROW(),2)=0)'],
                    fill=PatternFill("solid", fgColor="F3F6FA", bgColor="F3F6FA")))
    for col in ("C", "H"):
        for row in ws.iter_rows(min_row=2, max_row=end, min_col=ord(col) - 64, max_col=ord(col) - 64):
            for cell in row:
                cell.number_format = "#,##0"
                cell.font = Font(name=FONT, size=10, bold=(col == "H"))
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{last_col_letter}{last_row}"


def build_workbook(out, excluded, log, args, rules):
    wb = openpyxl.Workbook()

    # --- SMB database
    ws = wb.active
    ws.title = "SMB database"
    cols = lead_columns([
        ("Screening", lambda r: r["screening"]),
        ("Bron", lambda r: r["bron"]),
        ("Opmerking", lambda r: " | ".join(r["notes"])),
    ])
    for c, (h, _) in enumerate(cols, start=1):
        ws.cell(row=1, column=c, value=h)
    write_rows(ws, out, cols)
    last = len(out) + 1
    ws["H2"] = "=SUM(C:C)"
    style_header(ws, len(cols))
    add_formats(ws, last, "K")
    widths = [38, 34, 14, 30, 24, 20, 26, 14, 15, 11, 60]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws["A1"].comment = Comment(
        f"Bron: {args.smb_naam} ({log['smb_in']} rijen) en Zoho-export {args.zoho_naam} "
        f"({log['zoho_in']} rijen), geupload {args.datum}. Gefilterd met screening_regels.csv "
        f"en de colleguescreening ({args.gescreend_naam}). Zie tabblad Bronnen.", "SMB database")
    ws["C1"].comment = Comment(
        "Rood: ticketaantal ontbreekt of is 0. Vul het aantal in; de cel wordt dan wit "
        "en telt mee in het totaal in H2.", "SMB database")

    # --- Uitgesloten
    wx = wb.create_sheet("Uitgesloten")
    xcols = lead_columns([
        ("Bron", lambda r: r["bron"]),
        ("Moederorganisatie", lambda r: r["moeder"]),
        ("Reden", lambda r: r["reden"]),
        ("Gescreend door", lambda r: r["door"]),
        ("Verificatie", lambda r: r["verificatie"]),
        ("Opmerking", lambda r: " | ".join(r["notes"])),
    ])
    for c, (h, _) in enumerate(xcols, start=1):
        wx.cell(row=1, column=c, value=h)
    write_rows(wx, excluded, xcols)
    wx["H2"] = "=SUM(C:C)"
    style_header(wx, len(xcols))
    add_formats(wx, len(excluded) + 1, "N", red=False, blue=True)
    for i, w in enumerate([38, 34, 14, 30, 24, 20, 26, 14, 11, 30, 60, 34, 40, 40], start=1):
        wx.column_dimensions[get_column_letter(i)].width = w

    # --- Samenvatting
    sm = wb.create_sheet("Samenvatting")
    db, ux = "'SMB database'", "Uitgesloten"
    n = 10000
    lines = [
        ("SMB-leaddatabase, stand " + args.datum, None),
        (None, None),
        ("Legenda", None),
        ("Rode rij", "Ticketaantal ontbreekt of is 0. Vul kolom C in; het rood verdwijnt dan."),
        ("Oranje rij", "Te controleren: mogelijk onderdeel van een grotere organisatie."),
        ("Blauwe rij", "Tabblad Uitgesloten: landelijke sportbond, uitgesloten met hetzelfde criterium "
                       "als KNZB en NIJB. Controleer of ze terug moeten."),
        (None, None),
        ("Kerncijfers", "Waarde"),
        ("Leads in database", f"=COUNTA({db}!$A$2:$A${n})"),
        ("Totaal aantal tickets", f"=SUM({db}!$C$2:$C${n})"),
        ("Leads met ticketaantal", f"=COUNTIFS({db}!$A$2:$A${n},\"<>\",{db}!$C$2:$C${n},\">0\")"),
        ("Leads zonder ticketaantal (rood)", "=B9-B11"),
        ("Leads te controleren (oranje)", f"=COUNTIF({db}!$I$2:$I${n},\"{TE_CONTROLEREN}\")"),
        ("Uitgesloten leads", f"=COUNTA({ux}!$A$2:$A${n})"),
        ("Tickets van uitgesloten leads", f"=SUM({ux}!$C$2:$C${n})"),
        ("Uitgesloten sportbonden (blauw)", f"=COUNTIF({ux}!$J$2:$J${n},\"{SPORTBOND}\")"),
        (None, None),
    ]
    for r_i, (a, b) in enumerate(lines, start=1):
        sm.cell(row=r_i, column=1, value=a)
        sm.cell(row=r_i, column=2, value=b)

    def table(start_row, title, labels, col_letter):
        sm.cell(row=start_row, column=1, value=title)
        for c, h in enumerate(["Leads", "Tickets", "Te controleren"], start=2):
            sm.cell(row=start_row, column=c, value=h)
        for k, lab in enumerate(labels, start=start_row + 1):
            sm.cell(row=k, column=1, value=lab)
            rng = f"{db}!${col_letter}$2:${col_letter}${n}"
            sm.cell(row=k, column=2, value=f"=COUNTIF({rng},$A{k})")
            sm.cell(row=k, column=3, value=f"=SUMIF({rng},$A{k},{db}!$C$2:$C${n})")
            sm.cell(row=k, column=4, value=f"=COUNTIFS({rng},$A{k},{db}!$I$2:$I${n},\"{TE_CONTROLEREN}\")")
        tot = start_row + len(labels) + 1
        sm.cell(row=tot, column=1, value="Totaal")
        for c in (2, 3, 4):
            L = get_column_letter(c)
            sm.cell(row=tot, column=c, value=f"=SUM({L}{start_row + 1}:{L}{tot - 1})")
        return start_row, tot

    t1 = table(len(lines) + 1, "Per bron", ["SMB-lijst", "Zoho", "Beide"], "J")
    statuses = sorted({r["status"] for r in out if r["status"]})
    t2 = table(t1[1] + 2, "Per Lead Status", statuses, "G")
    no_status_row = t2[1] + 1
    sm.cell(row=no_status_row, column=1, value="Zonder Lead Status")
    sm.cell(row=no_status_row, column=2, value=f"=B9-B{t2[1]}")
    sm.cell(row=no_status_row, column=3, value=f"=B10-C{t2[1]}")

    door = sorted({r["door"] for r in excluded})
    t3 = no_status_row + 2
    sm.cell(row=t3, column=1, value="Uitgesloten per screening")
    sm.cell(row=t3, column=2, value="Leads")
    sm.cell(row=t3, column=3, value="Tickets")
    for k, lab in enumerate(door, start=t3 + 1):
        sm.cell(row=k, column=1, value=lab)
        sm.cell(row=k, column=2, value=f"=COUNTIF({ux}!$L$2:$L${n},$A{k})")
        sm.cell(row=k, column=3, value=f"=SUMIF({ux}!$L$2:$L${n},$A{k},{ux}!$C$2:$C${n})")
    t3_end = t3 + len(door) + 1
    sm.cell(row=t3_end, column=1, value="Totaal")
    sm.cell(row=t3_end, column=2, value=f"=SUM(B{t3 + 1}:B{t3_end - 1})")
    sm.cell(row=t3_end, column=3, value=f"=SUM(C{t3 + 1}:C{t3_end - 1})")

    head_rows = {1, 3, 8, t1[0], t2[0], t3}
    total_rows = {t1[1], t2[1], t3_end}
    for row in sm.iter_rows(min_row=1, max_row=t3_end, max_col=4):
        for cell in row:
            cell.font = Font(name=FONT, size=10)
            if cell.column > 1:
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right")
    for r_i in head_rows:
        for c in range(1, 5):
            cell = sm.cell(row=r_i, column=c)
            if r_i == 1:
                cell.font = Font(name=FONT, size=14, bold=True, color=NAVY)
            else:
                cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
                if r_i != 3:
                    cell.fill = PatternFill("solid", fgColor=NAVY)
                else:
                    cell.font = Font(name=FONT, size=10, bold=True, color=NAVY)
    for r_i in total_rows:
        for c in range(1, 5):
            sm.cell(row=r_i, column=c).font = Font(name=FONT, size=10, bold=True)
            sm.cell(row=r_i, column=c).border = Border(top=THIN)
    sm["A4"].fill = PatternFill("solid", fgColor="F4CCCC")
    sm["A5"].fill = PatternFill("solid", fgColor="FCE5CD")
    sm["A6"].fill = PatternFill("solid", fgColor=BLAUW)
    for ref in ("B4", "B5", "B6"):
        sm[ref].alignment = Alignment(horizontal="left")
    sm.column_dimensions["A"].width = 38
    for L in "BCD":
        sm.column_dimensions[L].width = 16

    # --- Bronnen
    br = wb.create_sheet("Bronnen")
    brows = [
        ["Bestand", "Inhoud", "Rijen", "Ontvangen", "Bewerkingen"],
        [args.smb_naam, "Officiele SMB-leadlijst", log["smb_in"], args.datum,
         "Gescreend op moederorganisatie; tekens met dubbele codering hersteld"],
        [args.gescreend_naam, "Colleguescreening (5.000-20.000 tickets)", log["gescreend_in"], args.datum,
         "Gebruikt om verwijderde leads en twijfelgevallen over te nemen"],
        [args.zoho_naam, "Zoho-export SMB-leads", log["zoho_in"], args.datum,
         "Gekoppeld op bedrijfsnaam; Zoho leidend voor tickets, status en ticketsolution; "
         "dubbele leads (zelfde bedrijf en aantal) samengevoegd; contactgegevens niet overgenomen"],
        ["screening_regels.csv", "Filterregels per moederorganisatie", len(rules), args.datum,
         "Opgesteld uit de colleguescreening, aangevuld voor leads onder 5.000 tickets en Zoho-leads"],
    ]
    for r_i, vals in enumerate(brows, start=1):
        for c_i, v in enumerate(vals, start=1):
            cell = br.cell(row=r_i, column=c_i, value=v)
            cell.font = Font(name=FONT, size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if r_i > 1 and c_i == 4:
                cell.number_format = "@"
    style_header(br, 5)
    for i, w in enumerate([46, 36, 10, 14, 80], start=1):
        br.column_dimensions[get_column_letter(i)].width = w

    # leesvolgorde: samenvatting eerst
    wb.move_sheet("Samenvatting", offset=-2)
    wb.active = 0
    wb.save(args.out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--smb", required=True)
    p.add_argument("--gescreend", required=True)
    p.add_argument("--zoho", required=True)
    p.add_argument("--regels", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--datum", default="24-11-2026")
    p.add_argument("--smb-naam", default="Small_to_medium_Business(Paylogic fit).csv")
    p.add_argument("--gescreend-naam", default="SMB_leads_gescreend.csv")
    p.add_argument("--zoho-naam", default="Leads_2026_11_24.xlsx")
    args = p.parse_args()

    out, excluded, log = build(args)
    log["gescreend_in"] = sum(load_gescreend(args.gescreend)[0].values())
    rules = load_rules(args.regels)
    build_workbook(out, excluded, log, args, rules)

    tc = sum(1 for r in out if r["screening"] == TE_CONTROLEREN)
    missing = sum(1 for r in out if not r["tickets"])
    print("Invoer:  SMB", log["smb_in"], "| Zoho", log["zoho_in"], "| gescreend", log["gescreend_in"])
    print("Zoho:    gekoppeld", log["zoho_gekoppeld"], "| alleen Zoho", log["zoho_alleen"],
          "| dubbel samengevoegd", log["zoho_dubbel"])
    print("SMB:     collega verwijderd", log["smb_collega_verwijderd"], "| regel verwijderd",
          log["smb_regel_verwijderd"], "| collega te controleren", log["smb_collega_te_controleren"],
          "| regel te controleren", log["smb_regel_te_controleren"])
    print("Zoho-only verwijderd", log["zoho_verwijderd"])
    print("Uitvoer: database", len(out), "| uitgesloten", len(excluded), "| te controleren", tc,
          "| zonder tickets", missing)
    print("Tickets: database", sum(r["tickets"] or 0 for r in out),
          "| uitgesloten", sum(r["tickets"] or 0 for r in excluded))
    # aansluiting: elke invoerrij is behouden, uitgesloten of samengevoegd
    smb_acc = len(smb_rows := [r for r in out + excluded if r["bron"] in ("SMB-lijst", "Beide")])
    zoho_acc = (sum(1 for r in out + excluded if r["bron"] in ("Zoho", "Beide"))
                + log["zoho_dubbel"])
    print("Aansluiting SMB:", smb_acc, "==", log["smb_in"], "| Zoho:", zoho_acc, "==", log["zoho_in"])
    assert smb_acc == log["smb_in"] and zoho_acc == log["zoho_in"], "aansluiting klopt niet"


if __name__ == "__main__":
    main()
