# De Amsterdamse Zomer 2027: promo-screenshots van de shop (zonder datum)

Dit zijn screenshots van de Paylogic-shop (REGULAR TICKETS, 10 juli 2027) waarin de datum onleesbaar is gemaakt.
Zo wordt "uitverkocht" niet gekoppeld aan de hele show: alleen de pre-sale is uitverkocht.

## Bestanden (`output/`)

| Bestand | Formaat | Gebruik |
|---|---|---|
| `…_ipad-pro-11_2388x1668.jpg` | 2388 × 1668 (1,43:1) | iPad Pro 11" / iPad Air in landscape (hoofdbestand) |
| `…_ipad-pro-12.9_2732x2048.jpg` | 2732 × 2048 (4:3) | iPad Pro 12,9" in landscape. Hierop staat de hele shop. |
| `…_volledige-pagina_2388w.jpg` | 2388 × 1876 | Hele pagina, om in Illustrator zelf bij te snijden (clipping mask) |

Van elk bestand staat er ook een `.png` (lossless) naast.
Bewust geen 1920 × 1080: een iPad-scherm is ongeveer 4:3, dus 16:9 wordt in het frame uitgerekt of fors bijgesneden.

## Wat is er aangepast

- **Header**: de tekst "10 jul 2027 17:00" is met CSS geblurd. Alleen de letters zijn aangepast, de achtergrond blijft scherp.
- **Productafbeeldingen** (MIVA Veld, Golden Circle - Rechts, Veldtickets): "ZATERDAG 10 JULI 2027" in het crèmekleurige labeltje
  is uitgevloeid (`soften_date.py`). Rand, lint, "SOLD OUT" en de rest van de afbeelding zijn pixel-gelijk aan het origineel.
- Cookiebanner weggeklikt. Al het andere is de echte, live shop.

## Opnieuw maken (bijvoorbeeld als de regular sale opent)

```bash
node capture.js            # schrijft naar ./output
```

Vereist zijn Playwright met Chromium, `curl` en python3 met numpy, pillow en scipy.
De blur stel je bij met omgevingsvariabelen:

```bash
HEADER_BLUR=5.5 HEADER_OPACITY=0.5 LABEL_SIGMA=9 LABEL_STRENGTH=0.35 node capture.js
```

`ONLY=ipad-pro-11` maakt alleen dat formaat. Het script stopt met een foutmelding als er nog ergens een datum als tekst leesbaar is.
