# Emergency Kit · Тривожна валіза

[Українська](README.md) · English

The Emergency Kit works on a Mac with no internet: official guides, medical libraries, a map of Ukraine and an AI that answers in Ukrainian. Everything runs on your own computer and nothing is sent anywhere.

## Install

*This part will be rewritten (ticket 13). Until then, see `install.sh` for the installation.*

<!-- user-guide:start -->
## Start here

1. Double-click the **Start** file in the kit folder (its name is in both languages). Leave the Terminal window that opens: the kit works while it stays open.
2. The **start page** opens in the browser at `http://localhost:8091`. It has:
    - **Urgent**: buttons for situations where every minute counts (severe bleeding, rubble, mines, carbon monoxide, radiation and more). A button opens the Official Guide first, then the WikiMed article.
    - **Search the libraries**: one box for all the libraries. English finds the most; there is also a button to search in Ukrainian.
    - **Ask the AI**: describe your situation in your own words.
    - **Map** and **Where am I?**: an offline map, address search, the nearest hospital, pharmacy and water.
    - **Official guides**: pages from the State Emergency Service, the Ministry of Health, the Public Health Center, the Red Cross and dovidka.info, saved for reading without internet, and the handbook "In case of emergency or war".
    - **Get ready**: **Print** and **Checklist** (see below).
3. **Language.** The **УКР | ENG** switch is at the top right of every page. Your choice is remembered on this device.
4. **The family's phones.** Connect them to the same Wi-Fi and open the address that the Terminal window shows (for example `http://192.168.1.23:8091`) in the browser. No internet is needed: the AI and the map work from a phone too, the Mac does the work. The router needs power: a power bank will keep it going for a long time.

| I need to... | Do this |
|---|---|
| Act fast on an injury or poisoning | Start page, **Urgent**. Call **112** if any phone works |
| Ask a question in plain words | **Ask the AI** |
| Ask about a photo (a wound, a rash, damage) | **Ask the AI**, the photo button (**Quick answer** mode) |
| Know what the authorities advise | **Official guides** |
| Find an address, a hospital, a pharmacy or water | **Map**, the search box or the Nearest buttons |
| Read off coordinates to pass on | **Map**, tap the place |
| Have the advice on paper | **Print** (while there is power) |
| Check that everything is ready at home | **Checklist** |

Numbers: **112** all emergencies · **101** fire and rescue · **102** police · **103** ambulance · **104** gas emergency.

## Using the AI

The AI runs entirely on the Mac. Open **Ask the AI** on the start page (or `http://localhost:8091/ai/`). The same page works on the family's phones on the Wi-Fi.

1. **Choose a mode** above the question box:

    | Mode | Use it when |
    |---|---|
    | **From sources** | Most of the time: injuries, illness, medicines, water, food, heat, the authorities' advice. The AI first finds the Official Guides, Books and Library articles that fit, answers from them and lists them under the answer. Tap a source to open it |
    | **Quick answer** | You are in a hurry, or you want to ask about a **photo**. The answer comes without a search for sources |
    | **Save battery** | The Mac is on battery. A smaller model and simpler answers; it takes photos too |

2. **Write as if you were phoning the rescue service:** who (age, a child's weight), what happened, when, what you see, what you have at home. Example: *My father is 72. He fell down the stairs 20 minutes ago and hit his head. He is bleeding a little from the forehead and seems confused. We have plasters, sterile gauze and paracetamol. What should we do?*
3. **Keep asking.** The AI remembers the conversation ("What if it gets worse?", "Explain step 3 more simply"). Start a new conversation when you change the subject.
4. **Photos:** good light, close up, one thing per picture, and write what you want to know.
5. **Speak instead of typing:** the Mac's dictation (the 🎤 key, or press Fn twice) or the microphone on the phone's keyboard.
6. **Check what matters.** The AI can be wrong. Open the source under the answer, especially for doses. Never eat a mushroom or plant because the AI says it is edible.
7. **Save power.** The AI uses a lot of power while it answers. Ask few, clear questions, choose Save battery and close other apps.
8. **If it does not work:** the line at the top of the AI page shows what is missing: the AI engine, the Book index or the libraries. Without the Book index, From sources searches only the Library articles. The first answer after starting takes longer.
9. **Privacy.** Your questions and the answers are never stored on the Mac.

The AI does not replace a doctor or the rescue service. If a life is at risk, call **112** and use the **Urgent** buttons instead of waiting for the AI. The AI will tell you to call **112** or **101** when a life is at risk. For a suspicious object it reminds you: do not touch it, mark the place, call **101**.

## The map

The offline map covers Ukraine and Moldova plus a strip of about 100 km into Poland, Slovakia, Hungary and Romania. Names are in Ukrainian and English. Inside that area it is detailed, down to single houses.

- **Search** for a town, village, street or address, for example *Khreshchatyk 22, Kyiv*. *Київ*, *Kyiv* and *Kiev* all work. If the map data has no house number, the pin is placed between the neighbouring houses and the map says the position is approximate.
- **Nearest** buttons list the nearest hospitals, pharmacies, fire stations, water and more from the centre of the map (or from you, when your position is known).
- **Where am I?** shows your position on the map with no internet. **The Mac has no GPS of its own**: plug in a **USB GPS receiver** (search for "USB GPS"; most use a u-blox chip) and, if the computer only has USB-C, an adapter. The first time, the receiver may need a few minutes by a window or outdoors. With no receiver you can lend a phone's position: open `/mobil/` on the phone, follow the steps for iPhone or Android, then turn lending on at the Mac. Lending stays off until the owner or the person running the Community Point turns it on.
- **Tap the map** to read off exact coordinates that you can pass on by radio or write down.

## Get ready

### Checklist

The **Checklist** on the start page helps you prepare step by step for a week without electricity, water and shops. It has three parts:

- **At home** and **What to put in the go-bag**: the official list from dovidka.info ("How to prepare for an emergency"), saved in the kit;
- **For the kit itself**: what the Emergency Kit needs (radio, power bank, GPS receiver, a map and libraries on a phone).

Tick what you already have. The ticks are kept in this device's browser. **Start over** clears them and **Print** prints the list. The dovidka.info list has separate Ukrainian and English versions, so their ticks are kept apart; the ticks for the kit itself are shared by both languages.

### Print

**Print** on the start page prepares a pack: first aid, wounds and bleeding, carbon monoxide, clean water, a radiation accident (the English pack differs a little, because not every guide exists in English). Print it **in the page's language** while there is power, and keep the sheets with the Emergency Kit. If the Mac has no power, paper is what you can still read. When there is internet, check the latest advice at dovidka.info, moz.gov.ua, phc.org.ua and redcross.org.ua.

This guide can be printed too: the files "Тривожна валіза - посібник для друку.pdf" (Ukrainian) and "Emergency Kit - printable guide.pdf" (English) are in the kit folder.

### Also do this

- Install **Organic Maps** on your phone and download the map of Ukraine: a second map that lasts days on a power bank.
- Install **Kiwix** on your phone and copy over the medical libraries.
- Get a battery or hand-crank radio, and a power bank for the Mac.
- Get a **USB GPS receiver** and test it once with **Where am I?** on the map.
- Offer older neighbours help with their preparations (dovidka.info advises it).

The Emergency Kit is not medical advice and does not replace the rescue service. In an emergency, call **112**.
<!-- user-guide:end -->

## The rest

*Sections on checking the kit, running a Community Point, licences and credits will be written in ticket 13. Credits and licences: `CREDITS.md`.*
