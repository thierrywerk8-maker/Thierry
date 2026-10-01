# Draaimolen Festival 2026: ticketshop Accommodations & Travel

Een visual briefing / vlekkenplan om de Travel & Camping-info van draaimolen.nu in de Paylogic-ticketshop te zetten.
Opbouw, segmentatie, productnamen en sub-info volgen de Dekmantel Festival 2026-shop (tabs *ACCOMODATIONS* en *SHUTTLE BUS*).
Alleen producten die Draaimolen nu al aanbiedt; geen nieuwe producten of bundels.

**Figma (vlekkenplan):** https://www.figma.com/design/9Rs7DdoUfvabBco7DMEjsG

| Frame | Inhoud |
|---|---|
| 00 · Cover & legenda | Doel, bronnen, legenda, overgenomen principes |
| 01 · Analyse Dekmantel-shop | Alle Dekmantel-producten (naam, sub-info, prijs, fee, status), anatomie, naamconventie, vertaling naar Draaimolen |
| 02 · Flow & koppelingen | Welk product wat vereist, plus de koppelregels voor Paylogic |
| 03 / 04 · Desktop | Tab ACCOMMODATIONS (kaarten met foto) en tab TRAVEL (regels zonder foto), met genummerde toelichting |
| 05 / 06 · Mobiel (390px) | Dezelfde twee tabs op mobiel |
| 07 · Productlijst voor Paylogic | Naam, subnaam, prijs, (i)-tekst en koppeling per product |
| 08 · Open punten | Wat Draaimolen nog moet bevestigen |

## Structuur van de shop

- **Tabs:** `TICKETS · ACCOMMODATIONS · TRAVEL` (Dekmantel: `TICKETS · ACCOMODATIONS · LOCKERS · SHUTTLE BUS`)
- **Header per tab:** titel · Draaimolen Festival 2026 · 4 – 5 sep 2026 · MOB Complex, Tilburg
- **ACCOMMODATIONS:** chips `ALLE · CAMPING · PRE-SET ACCOMMODATION`. Productkaarten met foto (3 per rij): NAAM (CAPACITEIT) + ⓘ, één regel sub-info, prijs incl. fee, regel "incl. € x servicekosten", stepper.
- **TRAVEL:** chips `ALLE · SHUTTLE BUS · PARKING · BIKES`. Lijstregels zonder foto: NAAM + ⓘ en sub-info links, prijs + servicekosten rechts, stepper.
- Trein/OV, Bolt/Uber Kiss & Ride en OV-fiets zijn geen producten en blijven info op de FAQ-pagina.

## Productlijst: om over te nemen in Paylogic

Shopprijs = basisprijs + € 3,90 servicekosten (FAQ: *"All ticket prices exclude a service fee of €3,90"*).
Volgens de FAQ is de pre-set accommodatie al inclusief servicekosten. Dezelfde data staat in
[`paylogic-products.csv`](paylogic-products.csv) (puntkomma-gescheiden, opent direct in Excel) en [`products.json`](products.json).

### Tab ACCOMMODATIONS

| # | Sectie | Naam | Subnaam | Prijs in shop | Opbouw |
|---|---|---|---|---|---|
| 1 | CAMPING | **CAMPING TICKET** | Stay at the Draaimolen campsite with your own tent. Thu 3 – Sun 6 Sept. | **€ 69,90** | € 66,00 + € 3,90 servicekosten |
| 2 | CAMPING | **CAMPER TICKET** | Stay with your own camper at the Draaimolen campsite. Thu 3 – Sun 6 Sept. | **€ 53,90** | € 50,00 + € 3,90 servicekosten |
| 3 | PRE-SET ACCOMMODATION | **FESTITENT (1 GUEST)** | Stay in a pre set up Festitent at the Draaimolen campsite. Thu – Sun (3 nights). | **€ 122,00** | incl. servicekosten (volgens FAQ) |
| 4 | PRE-SET ACCOMMODATION | **FESTITENT (2 GUESTS)** | Stay in a pre set up Festitent at the Draaimolen campsite. Thu – Sun (3 nights). | **€ 177,00** | incl. servicekosten (volgens FAQ) |
| 5 | PRE-SET ACCOMMODATION | **FESTITENT (4 GUESTS)** | Stay in a pre set up Festitent at the Draaimolen campsite. Thu – Sun (3 nights). | **€ 355,00** | incl. servicekosten (volgens FAQ) |
| 6 | PRE-SET ACCOMMODATION | **LODGE (2 GUESTS)** | Stay in a pre set up Lodge at the Draaimolen campsite. Thu – Sun (3 nights). | **€ 444,00** | incl. servicekosten (volgens FAQ) |
| 7 | PRE-SET ACCOMMODATION | **BELLTENT (4 GUESTS)** | Stay in a pre set up Belltent at the Draaimolen campsite. Thu – Sun (3 nights). | **€ 610,00** | incl. servicekosten (volgens FAQ) |

### Tab TRAVEL

| # | Sectie | Naam | Subnaam | Prijs in shop | Opbouw |
|---|---|---|---|---|---|
| 8 | SHUTTLE BUS | **SHUTTLE BUS ROUND TRIP STATION – CAMPING** | Buses depart from Tilburg Central Station (Spoorlaan 444) to the campsite | **€ 8,90** | € 5,00 + € 3,90 servicekosten |
| 9 | SHUTTLE BUS | **SHUTTLE BUS ROUND TRIP CAMPING – FESTIVAL** | Buses depart from the campsite to the festival on Friday & Saturday | **€ 8,90** | € 5,00 + € 3,90 servicekosten |
| 10 | PARKING | **PARKING TICKET** | Park at Quirijnstokstraat 10, across the street from the campsite | **€ 23,90** | € 20,00 + € 3,90 servicekosten |
| 11 | BIKES | **BIKE RENTAL** | Rent a bike at the campsite. Excl. € 50 deposit | **€ 33,90** | € 30,00 + € 3,90 servicekosten |

### (i)-teksten (popup) en koppelingen

- **CAMPING TICKET**: Camping tickets are sold separately from festival tickets – make sure you have both if you plan to stay overnight. Every person staying at the campsite needs a camping ticket, regardless of accommodation type. Includes access to all campsite facilities. One camping ticket = one tent: bring your own tent at no extra cost. No ticket sales at the entrance. Re-entry between festival and campsite is allowed. _Koppeling: Festivalticket nodig (los / uitverkocht → alleen communiceren)._
- **CAMPER TICKET**: Required per camper vehicle. This does not include a camping ticket – each person in the camper must also have a camping ticket. A caravan is not allowed. Once your camper is set up, you cannot leave and return. _Koppeling: Camping Ticket per persoon in de camper._
- **FESTITENT (1 GUEST)**: Pre set up tent for 1 person, which can include upon preference a tent, air mattress, sleeping bag, pillow and lantern. 3 nights, Thursday until Sunday. Camping ticket not included – you also need a camping ticket. Cancellation via info@festitent.com: free up to 30 days before the festival; from 30 days up to 5 working days before, a € 15 cancellation fee applies; within 5 working days only the deposit is refunded. _Koppeling: 1 × Camping Ticket._
- **FESTITENT (2 GUESTS)**: Pre set up tent for 2 persons, which can include upon preference a tent, air mattresses, sleeping bags, pillows and a lantern. 3 nights, Thursday until Sunday. Camping tickets not included – every guest needs a camping ticket. Cancellation via info@festitent.com: free up to 30 days before the festival; from 30 days up to 5 working days before, a € 15 cancellation fee applies; within 5 working days only the deposit is refunded. _Koppeling: 2 × Camping Ticket._
- **FESTITENT (4 GUESTS)**: Pre set up tent for 4 persons, which can include upon preference a tent, air mattresses, sleeping bags, pillows and lanterns. 3 nights, Thursday until Sunday. Camping tickets not included – every guest needs a camping ticket. Cancellation via info@festitent.com: free up to 30 days before the festival; from 30 days up to 5 working days before, a € 15 cancellation fee applies; within 5 working days only the deposit is refunded. _Koppeling: 4 × Camping Ticket._
- **LODGE (2 GUESTS)**: Pre set up tent (2,5 × 3 m) for 2 persons with two separate beds with mattresses, duvets and bedding, a doormat, 2 chairs and lanterns. Well ventilated, protects you from sun and rain, plenty of space for your luggage. Electricity included. 3 nights, Thursday until Sunday. Camping tickets not included – both guests need a camping ticket. _Koppeling: 2 × Camping Ticket._
- **BELLTENT (4 GUESTS)**: Pre set up bell tent (diameter 5 m) for 4 persons with a carpet, beds with mattresses, duvets and bedding, and lanterns. Plenty of space for your luggage. Electricity included. 3 nights, Thursday until Sunday. Camping tickets not included – every guest needs a camping ticket. _Koppeling: 4 × Camping Ticket._
- **SHUTTLE BUS ROUND TRIP STATION – CAMPING**: Includes both directions. Pick-up point: Spoorlaan 444, 5038 CH Tilburg (Tilburg Central Station). Thu 3 Sept 15:00 – 23:00: every hour. Fri 4 Sept 09:00 – 14:00: every 30 minutes; 14:00 – 17:00: every hour on the hour. Sun 6 Sept 08:00 – 13:00: hop on at your preferred time, at least 2 buses per hour. _Koppeling: Geen._
- **SHUTTLE BUS ROUND TRIP CAMPING – FESTIVAL**: Includes both directions. Hop on at the campsite. Fri 4 Sept: 12:00 – 18:00 and 21:00 – 01:30. Sat 5 Sept: 12:00 – 18:00 and 21:00 – 01:30. _Koppeling: Bedoeld voor campinggasten (Camping Ticket)._
- **PARKING TICKET**: For visitors arriving by car. Parking address: Quirijnstokstraat 10, Tilburg – the campsite is right across the street from the parking lot. This does not include a camping ticket. _Koppeling: Geen (camping ticket niet inbegrepen)._
- **BIKE RENTAL**: Rental bike, available at the campsite. Excl. € 50 deposit. Ideal if you're attending the opening concert or afterparties in the city centre. Limited availability. _Koppeling: Geen (borg € 50 apart)._

## Open punten

1. In de FAQ staat pre-set accommodatie **van € 89 tot € 610**, maar het goedkoopste product dat genoemd wordt is Festitent 1p (€ 122). Welk product kost € 89?
2. Accommodatie wordt nu via een externe Festitent-link verkocht. Komt dit echt in Paylogic, en wie is de verkopende partij (annuleringsvoorwaarden)?
3. Wordt de servicefee van € 3,90 per product gerekend, ook op de shuttle van € 5? Welk deel van de accommodatieprijzen is servicekosten?
4. Shuttle Camping – Festival: één retour voor het hele weekend of per dag (zoals Dekmantel FRIDAY / SATURDAY)?
5. Shuttle Station – Camping: is zondag 08:00–13:00 de terugrit naar het station?
6. Parking Ticket: per voertuig? Geldig voor het hele weekend of per dag?
7. Bike Rental: hoe gaat de borg van € 50 (apart product of ter plekke)?
8. Foto's aanleveren voor Camping Ticket en Camper Ticket.
9. Maximaal aantal per bestelling per product.

## Bestanden

- `reference/dekmantel-shop.jpg` en `reference/draaimolen-faq.jpg`: de bronbeelden (uit de aangeleverde PDF's)
- `assets/festitent-1.jpg`, `festitent-4.jpg`, `lodge.jpg`, `belltent.jpg`: productfoto's uit de Draaimolen-FAQ (4:3).
  In Figma staan hier nog placeholders, omdat uploaden vanuit deze omgeving geblokkeerd was. Sleep ze op de kaarten.
