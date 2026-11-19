# Emergency Kit · Тривожна валіза

[Українська](README.md) · English

The Emergency Kit works on a Mac with no internet: official guides, medical libraries, a map of Ukraine and an AI that answers in Ukrainian. Everything runs on your own computer and nothing is sent anywhere.

## Install

You need: a Mac with an Apple chip (M1 or newer), **55 GB of free space** and internet while it installs. The kit itself takes about 45 GB: Libraries about 13 GB, the map about 3 GB, the AI models about 27 GB, the Books and index about 1 GB. Installing takes a few hours, mostly downloading. After that no internet is needed.

**Option 1: double-click.**

1. Download the kit's archive, unpack it and double-click **"Встановити - Install.command"**. If macOS will not open it, right-click the file, choose **Open** and confirm.
2. A Terminal window opens. Every message in it is one line in both languages: "Завантажую бібліотеки / Downloading libraries". Keep the window open until you see **Готово / Done**.

**Option 2: one line in Terminal.**

```
curl -fsSL https://raw.githubusercontent.com/IsacHassle/Ukrainian-emergency-kit/main/get.sh | bash
```

**What the installation does.** It first checks the Mac: it needs an Apple chip and 55 GB free, otherwise it stops before downloading anything. Then, in steps: 1) tools, 2) the Libraries (each checked against Kiwix's checksum), 3) the map and the map search, 4) the Official Guides and the Books, 5) the Ollama and AnythingLLM apps, the AI models and the Book index. The kit ends up in `~/Emergency-Kit` and a **"Тривожна валіза"** shortcut appears on the Desktop. If the archive sits in Downloads, the folder moves itself to `~/Emergency-Kit`.

**Interrupted?** By a power cut or a lost connection: double-click **Install** again. It continues where it stopped and skips what is already done.

**Without the AI** (about 20 GB): run `./install.sh --no-ai` in Terminal in the kit folder.

**If the State Emergency Service (ДСНС) site does not answer** from abroad (it often does not), the installation skips its pages and says so. The other Official Guides are saved.

The Ollama and AnythingLLM installers are kept in `installers/`, so that the kit can later be put on another Mac with no internet (a Kit Drive, later).

**Double-click files** in the kit folder (their names are in both languages):

| File | What it does |
|---|---|
| **Встановити - Install.command** | Installs the kit (or continues an interrupted installation) |
| **Запустити - Start.command** | Starts the kit and opens the start page |
| **Перевірити - Check.command** | Says what works and what is missing (see "Check" below) |

<!-- user-guide:start -->
## Start here

1. Double-click the file **"Запустити - Start.command"** in the kit folder (`~/Emergency-Kit`, with a "Тривожна валіза" shortcut on the Desktop). Leave the Terminal window that opens: the kit works while it stays open.
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
| Make sure the kit works | Double-click **"Перевірити - Check.command"** once a month |

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
- **Where am I?** shows your position on the map with no internet. **The Mac has no GPS of its own**: plug in a **USB GPS receiver** (search for "USB GPS"; most use a u-blox chip) and, if the computer only has USB-C, an adapter. The first time, the receiver may need a few minutes by a window or outdoors. With no receiver you can lend a phone's position: open `/phone/` on the phone, follow the steps for iPhone or Android, then turn lending on at the Mac. Lending stays off until the owner or the person running the Community Point turns it on.
- **Tap the map** to read off exact coordinates that you can pass on by radio or write down.

## Community Point (for the Keeper)

A **Community Point** is any place where a Kit Mac serves people outside your household: a shelter, a school, an Invincibility Point (Пункт незламності). The **Keeper** is the person who runs it. No internet is needed: you need the Mac, any Wi-Fi router and power.

1. **The router.** Give the router power and connect it to nothing else: a router with no internet is enough. It uses a few watts, so a power bank or a UPS keeps it going for many hours. Set a Wi-Fi password.
2. **The Mac.** Connect the Mac to this network, give it power and start the kit (**Запустити - Start.command**). Leave the Terminal window open. In the Mac's settings, stop it from sleeping while it is on mains power, and keep a power bank for the Mac close by.
3. **The poster.** On the Mac itself, open `http://localhost:8091/poster/` (it does not open from phones). Type the Wi-Fi name and password and print: one A4 sheet with two QR codes (join the Wi-Fi, open the kit), the address written out and the emergency numbers. The password lives only in the open page and is never saved or sent. Check that a phone on the network opens the address, and put the poster where people see it.
4. **The people.** Visitors join the Wi-Fi with the first code and open the kit with the second. What they see runs in their own browser; the Mac does the work.
5. **The AI is the slowest part.** When many people are there, ask them to use the **Urgent** buttons and the Libraries first: those answer at once.
6. **Lending a phone's position.** Lending is off until you turn it on **at the Mac itself** on the page `http://localhost:8091/phone/`. Other devices cannot. Turn it off when you leave: every lent position is erased.
7. **Privacy.** Visitors' questions to the AI are never stored. There is nothing to wipe when the Mac passes to someone else.
8. **Paper.** Keep this guide and the **Print** pack printed nearby, so that people have the advice even when the Mac's battery is empty.

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

## Check

Double-click **Перевірити - Check.command** once a month, best with Wi-Fi turned off. Every line is in both languages: ✅ works, ⚠️ missing or not working (the line says what to do), ℹ️ for your information. It looks at:

- **Libraries**: whether all are there and kiwix-serve is present;
- **the map**: whether both map files are whole, whether the map search is there, whether the certificate for the phone's GPS exists and whether a USB GPS receiver is connected;
- **documents**: how many Official Guides (texts and PDFs) and Books there are;
- **the AI**: whether Ollama runs, whether both models `emergency` and `emergency-small` and the model bge-m3 are there, whether the AI answers a test question, how many Books are in AnythingLLM's index;
- **space and power**: free disk space and the battery.

If something is marked ⚠️, running **Install** again usually helps: it downloads only what is missing.

## Known limits

- English labels on the map in Crimea come from OpenStreetMap (`name:en`) and are mostly Russian transliterations (Armyansk, Dzhankoy). This is a limit of the data. The Ukrainian names are correct.
- Not every shelter is on the map: OpenStreetMap marks only some. The Nearest page says so every time. Follow local signs and listen to the authorities too.
- Russian street names find the street but not an address with a house number.
- On the English page the Red Cross source name is still in Cyrillic ("Червоний Хрест"), and a few Red Cross pages about mines keep some stray lines from the site ("Останні новини", "Підписатись").
- The State Emergency Service (ДСНС) site does not answer from abroad, so its pages are saved only where it is reachable.
- The Mac has no GPS of its own: you need a USB GPS receiver or a lent phone position.
- The AI can be wrong. Check the sources under the answer, especially medicine doses.
- The kit runs only on a Mac with an Apple chip. Windows and Android are not supported.
- The Ukrainian texts are still waiting for a native speaker's review.

## Credits and licences

The kit's code is under the MIT licence (`LICENSE`). Everything the installation downloads (the Kiwix Libraries, the map from OpenStreetMap data, the Official Guides, the apps, the AI models) keeps its own licence and is not redistributed from this repository. The full list: [`CREDITS.md`](CREDITS.md).

The kit is built from the Swedish kit [Swedish-doomsdaykit](https://github.com/IsacHassle/Swedish-doomsdaykit) (MIT) and inspired by [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) (Crosstalk Solutions, Apache 2.0). The Official Guides belong to their authors: dovidka.info, the Ministry of Health, the Public Health Center, the Ukrainian Red Cross and the State Emergency Service. Each user saves them on their own Mac from the authority's site.
