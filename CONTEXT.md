# Emergency Kit / Тривожна валіза

An offline crisis kit for civilians in Ukraine: libraries, official guides, a map and a local AI on one Mac,
shared over Wi-Fi with the people around it.

## People, devices and places

**Kit Mac**:
The Mac the kit is installed on and runs from.
_Avoid_: server, host, the computer

**Visitor device**:
Any phone or laptop that uses the kit over Wi-Fi through a browser.
_Avoid_: client, guest

**Community Point**:
Any place where a Kit Mac serves people outside its owner's household. Shelters, schools and the official
Invincibility Points (Пункти незламності) are kinds of Community Point.
_Avoid_: hub, station, shelter (as a general term)

**Keeper**:
The person who runs a Kit Mac at a Community Point.
_Avoid_: admin, operator, host

**Lent position**:
A position a Visitor device sends to the Kit Mac, because the Kit Mac has no GPS of its own. Only accepted after
the Keeper or owner turns lending on at the Kit Mac.
_Avoid_: phone share, shared GPS

## Content

**Library**:
A Kiwix collection, such as WikiMed or MDWiki. People browse and search it; the AI looks up articles in some
of them.
_Avoid_: ZIM (outside code), database

**Book**:
A single document in the AI's index: a PDF taken out of a Library, an NHS Medicines page, or an Official Guide.
_Avoid_: document, file, source

**Official Guide**:
A page or handbook from a Ukrainian authority, saved when the kit is installed. Every Official Guide is also
a Book.
_Avoid_: authority page, government page

**Emergency Topic**:
A one-tap entry on the start page for an urgent situation (bleeding, rubble, mines). It opens the Official
Guide first and the WikiMed article second.
_Avoid_: quick link, akut

## The AI

**From sources** (З джерел):
The AI mode that first finds Books and Library articles for the question, answers from them and lists them.
_Avoid_: books mode, RAG, Ur böckerna

**Quick answer** (Швидка відповідь):
The AI mode that answers from the model alone, without sources. It can look at photos.

**Save battery** (Економія батареї):
Quick answer with the smaller model, for a Kit Mac on battery.

## Getting the kit

**Kit Drive**:
A USB drive made from an installed kit, which installs the whole kit on another Mac with no internet.
_Avoid_: USB stick, installer drive, backup
