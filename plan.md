# Τεχνικό & Παραγωγικό Σχέδιο Υλοποίησης: "Kara Loft and the Illuminati"
### Πλατφόρμα Στόχος: Amstrad CPC 6128 (128 KB RAM, Z80 @ 4 MHz, AY-3-8912, Mode 0)
### Σύστημα Ανάπτυξης: RASM, iDSK, Blender (MCP), Aseprite (MCP), Python Audio Pipeline

---

## 1. Σύνοψη Έργου & Προδιαγραφές

### 1.1 Game Overview
* **Τίτλος:** *Kara Loft and the Illuminati*
* **Είδος:** Action Platformer / Shoot 'em up / Adventure Puzzle
* **Hardware Target:** Amstrad CPC 6128 (128 KB RAM υποχρεωτικά, Floppy 3" / DSK image)
* **Οπτικό Mode:**
  * **In-Game:** Mode 0 (160 × 200 pixels, 16 χρώματα ταυτόχρονα από παλέτα 27).
  * **Title Screen:** Overscan Mode 0 (192 × 272 pixels, πλήρης οθόνη χωρίς borders, ~26 KB VRAM).
* **Πρωταγωνίστρια:** Kara Loft (διαστάσεις sprite: 16 pixels πλάτος × 48 pixels ύψος).
* **Οπλισμός:** Dual Pistols (2 πιστόλια, ανεξάρτητοι γεμιστήρες 7 σφαιρών έκαστο = 14 βολές πριν από πλήρες reload).
* **Υπόθεση:** Οι Illuminati προσπαθούν να αποτρέψουν την Kara από το να διεισδύσει στο τροχιακό αρχηγείο τους («The Illuminati») και να ανακτήσει τον αστρικό χάρτη με τις συντεταγμένες όπου κρατείται αιχμάλωτος ο πατέρας της.

---

## 2. Αρχιτεκτονική Περιβαλλόντων & Ροή Παιχνιδιού

Το παιχνίδι αποτελείται από έξι (6) διαδοχικά περιβάλλοντα με διαφορετικό τύπο scrolling και μηχανικές:

```
[Πόλη] (H-Scroll) 
   │  (Μετάβαση: Αυτοκίνητο)
   ▼
[Δάσος] (H-Scroll) 
   │  (Μετάβαση: Είσοδος σε σπήλαιο βάσης βουνού)
   ▼
[Σπηλιά] (V-Scroll: Κάτω -> Πάνω) 
   │  (Μετάβαση: Κατακλυσμός νερού)
   ▼
[Υποθαλάσσιο] (V-Scroll: Πάνω -> Κάτω) 
   │  (Μετάβαση: Έξοδος καταρράκτη σε όαση)
   ▼
[Έρημος] (H-Scroll) 
   │  (Μετάβαση: Εκτόξευση πυραύλου / διαστημοπλοίου)
   ▼
[Διαστημικός Σταθμός] (H-Scroll) 
   │  (Boss Room: Illuminati Master & ανάκτηση χάρτη)
   ▼
[Τέλος - Premise για Sequel]
```

### Αναλυτικός Πίνακας Επιπέδων

| Level | Περιβάλλον | Scrolling | Μηχανική Παιχνιδιού & Puzzles | Assets / Εχθροί | Μετάβαση |
|---|---|---|---|---|---|
| **1** | **Πόλη** | Horizontal (L $	o$ R) | Gunplay, άλματα σε ταράτσες, εύρεση κλειδιού για είσοδο σε υπόγειο γκαράζ | Illuminati Agents (κοστούμια), Drones, Κλειδιά, Ammo | Cutscene: Διαφυγή με muscle car προς την περιφέρεια |
| **2** | **Δάσος** | Horizontal (L $	o$ R) | Πλατφόρμες σε κλαδιά, παγίδες με ακίδες, τοποθέτηση αγαλματιδίου σε βωμό για απενεργοποίηση παγίδας | Illuminati Snipers, Άγρια θηρία, Βωμοί, Αγαλματίδια | Είσοδος σε σκοτεινό άνοιγμα σπηλαίου στη ρίζα βουνού |
| **3** | **Σπηλιά** | Vertical (Bottom $	o$ Top) | Ανάβαση σε πλατφόρμες/stalagmites, γρίφος με εξώφυλλα αρχαίων βιβλίων για άνοιγμα πύλης | Illuminati Excavators, Νυχτερίδες, Βιβλία, Σύμβολα | Σεισμός: Υπόγειες πηγές σπάνε, η σπηλιά πλημμυρίζει |
| **4** | **Υποθαλάσσιο** | Vertical (Top $	o$ Bottom) | Κατάδυση με μηχανική άνωσης/οξυγόνου, αποφυγή ναρκών και ηλεκτροφόρων καλωδίων | Υποβρύχια drones, Νάρκες, Medkits, Οξυγόνο | Έξοδος από υποθαλάσσιο σιφώνι που ξεχύνεται σε όαση |
| **5** | **Έρημος** | Horizontal (L $	o$ R) | Κινούμενη άμμος, αλληλεπίδραση με φιλικούς NPCs με χρήση νομισμάτων για πληροφορίες/κωδικούς | Νομάδες/Πληροφοριοδότες (NPCs), Illuminati Mercenaries, Coins | Είσοδος σε μυστική βάση εκτόξευσης & επιβίβαση σε σκάφος |
| **6** | **Διαστημικός Σταθμός** | Horizontal (L $	o$ R) | High-tech παγίδες λέιζερ, βαριά εξοπλισμένοι φρουροί, τελικός υπολογιστής χάρτη | Elite Cyber-Illuminati, Turrets, Keycards | Ανάκτηση Χάρτη Πατέρα & Cutscene απόδρασης με escape pod |

---

## 3. Μηχανικές Gameplay & Συστήματα

### 3.1 Kara Loft Sprite & Ballistics
* **Διαστάσεις:** 16 pixels πλάτος × 48 pixels ύψος.
  * Στο Mode 0: 2 pixels ανά byte $	o$ **8 bytes πλάτος** ανά γραμμή σάρωσης.
  * Μέγεθος frame: $48 	imes 8 = 384$ bytes δεδομένων + 384 bytes μάσκα (AND mask) = 768 bytes/frame.
* **Dual Pistols System:**
  * Όπλο 1 (Αριστερό): 7 σφαίρες.
  * Όπλο 2 (Δεξί): 7 σφαίρες.
  * Ρυθμός βολής: Εναλλάξ βολή (Left $	o$ Right $	o$ Left...).
  * HUD Display: Δύο σειρές από 7 bullets indicators.
  * Reload Trigger: Χειροκίνητο (Down + Fire) ή αυτόματο όταν και τα δύο όπλα φτάσουν στο 0. Χρόνος reload: 1.2 δευτερόλεπτα (penalty freeze ή περπάτημα με μειωμένη ταχύτητα).

### 3.2 Αντικείμενα & Αλληλεπιδράσεις (Interactive Matrix)
1. **Κλειδιά (Keys):** Μονόδρομη χρήση σε κλειδωμένες πόρτες/πύλες.
2. **Βιβλία (Lore Books):** Εξέταση εξωφύλλου (`Action button`). Το εξώφυλλο αποκαλύπτει 3 σύμβολα (π.χ. Ήλιος, Τρίγωνο, Μάτι). Η αντιστοίχιση των συμβόλων σε μοχλούς ξεκλειδώνει το πέρασμα.
3. **Αγαλματίδια (Statues):** Σήκωμα και μεταφορά. Τοποθέτηση σε πέτρινη βάση (Pressure Plate) για μόνιμη απενεργοποίηση παγίδων (π.χ. ακίδες, φλόγες, ηλεκτρικά πεδία).
4. **Νομίσματα (Coins):** Χρήση σε φιλικούς NPCs. Προσέγγιση $	o$ Πάτημα `Up` $	o$ Αφαίρεση νομίσματος $	o$ Εκτύπωση hint string στο κάτω μέρος της οθόνης.
5. **Σφαίρες (Ammo Clips):** Προσθέτουν 14 σφαίρες στο απόθεμα.
6. **Φαρμακεία (Medkits):** Επαναφορά 35% της μέγιστης ζωής (HP 0-100).

---

## 4. Τεχνικό Υπόβαθρο Amstrad CPC 6128

### 4.1 Memory Layout (128 KB Architecture)
Ο CPC 6128 ελέγχει τα πρόσθετα 64 KB μέσω της θύρας Gate Array `&7Fxx`:
* **Base 64 KB (`&0000 - &FFFF`):**
  * `&0000 - &003F`: Z80 Restart Vectors & Interrupt Service Routine (IM 1).
  * `&0040 - &3FFF`: Core Engine, Scrolling Engine, Sound Driver (Arkos AKG).
  * `&4000 - &7FFF`: Level Logic, Collision Data, Entity Management.
  * `&8000 - &BFFF`: Active Sprite Buffers, Restorations, Temp buffers.
  * `&C000 - &FFFF`: Primary Video RAM (16 KB standard frame buffer).
* **Extended 64 KB (Banks C4, C5, C6, C7):**
  * **Bank C4 (`&4000 - &7FFF` banked):** Level 1 & 2 Tiles, Tilemaps, Palette animations.
  * **Bank C5 (`&4000 - &7FFF` banked):** Level 3 & 4 Tiles, Subsea physics tables.
  * **Bank C6 (`&4000 - &7FFF` banked):** Level 5 & 6 Tiles, Space station assets.
  * **Bank C7 (`&4000 - &7FFF` banked):** Overscan Title Screen Buffer (26 KB διαμοιρασμένα σε 2 banks) & NPC dialogue tables.

### 4.2 Pixel Encoding Mode 0
Στο Mode 0, κάθε byte περιέχει 2 pixels. Τα bits των δύο pixels είναι μπλεγμένα (interleaved):
$$	ext{Pixel 0: } \{D1, D5, D3, D7\} \quad 	ext{και} \quad 	ext{Pixel 1: } \{D0, D4, D2, D6\}$$
Κάθε ρουτίνα εξαγωγής γραφικών από Aseprite/Blender πρέπει να ακολουθεί αυστηρά αυτόν τον πίνακα αντιστοίχισης:
* Bit 7: Pixel 0, bit 3
* Bit 6: Pixel 1, bit 3
* Bit 5: Pixel 0, bit 1
* Bit 4: Pixel 1, bit 1
* Bit 3: Pixel 0, bit 2
* Bit 2: Pixel 1, bit 2
* Bit 1: Pixel 0, bit 0
* Bit 0: Pixel 1, bit 0

### 4.3 Overscan Screen (192 × 272)
* CRTC Registers setup:
  * R0 (Horizontal Total) = 63
  * R1 (Horizontal Displayed) = 48 (48 chars × 4 bytes = 192 bytes = 384 Mode 1 pixels / 192 Mode 0 pixels)
  * R2 (Horizontal Sync Pos) = 50
  * R6 (Vertical Displayed) = 34 (34 chars × 8 scanlines = 272 scanlines)
  * R7 (Vertical Sync Pos) = 35

---

## 5. Βήμα-Βήμα Σχέδιο Τροφοδοσίας του AI (Prompting Pipeline)

Για να μην «χαθεί» το AI και να παράγει άριστο κώδικα Z80 χωρίς bugs, πρέπει να του δίνεις τα παρακάτω modules **ένα-ένα**. Μην προχωράς στο επόμενο αν δεν έχει γίνει compile και δοκιμή του προηγούμενου.

```
┌─────────────────────────────────────────────────────────────┐
│ MODULE 1: Memory Architecture, Build System (RASM/iDSK)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ MODULE 2: Asset Exporters (Blender MCP & Aseprite MCP)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ MODULE 3: Sprite Blitter, Masking & Dual Pistol Bullet Pool │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ MODULE 4: Dual Scrolling Engine (H-Scroll & V-Scroll)       │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ MODULE 5: Game Objects, Triggers, NPCs & Puzzle Matrix      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ MODULE 6: FSM Level Transitions & Cutscenes Engine          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ MODULE 7: 3-Channel AY-3-8912 Audio & SFX Priority Engine   │
└─────────────────────────────────────────────────────────────┘
```

---

### MODULE 1: Αρχιτεκτονική Μνήμης, Banking & Build Pipeline

#### Στόχος
Δημιουργία του βασικού skeleton του project, scripts μεταγλώττισης με `rasm`, δημιουργία `.dsk` με `idsk`, και ρουτίνες εναλλαγής RAM banks (Gate Array `&7Fxx`).

#### Prompt προς το AI
```markdown
Λειτούργησε ως Principal Software Engineer με ειδίκευση σε Z80 Assembly για τον Amstrad CPC 6128.
Θέλουμε να δημιουργήσουμε τη δομή του project "Kara Loft and the Illuminati".

Τεχνικές απαιτήσεις:
1. Χρήση του RASM assembler και του εργαλείου iDSK.
2. Target: 128 KB RAM.
3. Ορισμός Base RAM (&0000-&FFFF) και Extended Banks (&7FC4, &7FC5, &7FC6, &7FC7).
4. Υλοποίηση ασφαλών συναρτήσεων Bank Switching:
   - `BANK_SET_C4`: ενεργοποιεί το bank C4 στο διάστημα &4000-&7FFF
   - `BANK_SET_C5`: ενεργοποιεί το bank C5 στο διάστημα &4000-&7FFF
   - `BANK_SET_C6`: ενεργοποιεί το bank C6 στο διάστημα &4000-&7FFF
   - `BANK_RESTORE`: επαναφέρει την προεπιλεγμένη μνήμη (&7FC0).
5. Δημιούργησε:
   - `main.asm`: Βασικό σημείο εισόδου, αρχικοποίηση στοίβας (Stack Pointer στο &BFFF), ρύθμιση Interrupt Mode 1.
   - `build.sh` (ή Makefile): Script που κάνει compile με `rasm main.asm -o game.bin`, δημιουργεί κενό dsk με `idsk game.dsk -n`, εισάγει έναν BASIC loader (`disc.bas`) και το εκτελέσιμο `game.bin` με execution address &4000.

Δώσε πλήρη, σχολιασμένο κώδικα Assembly και το build script.
```

---

### MODULE 2: Asset Pipeline μέσω MCP (Blender & Aseprite)

#### Στόχος
Αυτοματοποιημένη μετατροπή 3D render από Blender σε 192×272 Overscan Mode 0 binary, και εξαγωγή 16×48 sprites από Aseprite με σωστό CPC Mode 0 pixel interleaving και μάσκες διαφάνειας.

#### Prompt προς το AI
```markdown
Χρειαζόμαστε τα scripts επεξεργασίας γραφικών για το pipeline μας, επικοινωνώντας με Blender MCP και Aseprite MCP:

1. Python Script για Blender MCP:
   - Ρυθμίζει την κάμερα σε Orthographic, Resolution 192 x 272 pixels.
   - Χρησιμοποιεί την επίσημη 27-χρωμη παλέτα hardware του Amstrad CPC.
   - Εφαρμόζει quantization στα επιλεγμένα 16 χρώματα του Mode 0 για την εισαγωγική οθόνη.
   - Εξάγει ένα raw binary αρχείο 26.112 bytes (`overscan.bin`), έτοιμο να φορτωθεί απευθείας στα buffers της VRAM με διάταξη CRTC scanlines (&C000 και &4000/&0000).

2. Script/Tool για Aseprite (Python ή Lua):
   - Επεξεργάζεται το sprite sheet της Kara Loft (16 pixels πλάτος x 48 pixels ύψος ανά frame).
   - Κωδικοποιεί τα pixels σύμφωνα με το hardware bit-interleaving του CPC Mode 0 (2 pixels ανά byte, 8 bytes ανά γραμμή).
   - Παράγει δύο πίνακες ανά frame:
     a) DATA buffer: Τα bytes των pixels.
     b) MASK buffer: 1-bit AND mask για κάθε pixel (0 όπου υπάρχει sprite pixel, 1 όπου υπάρχει διαφάνεια).
   - Αποθηκεύει το αποτέλεσμα σε binary format συμβατό με `INCBIN` του RASM (`kara_sprites.bin`).

Δώσε τα scripts με πλήρη τεκμηρίωση των bitwise shifts.
```

---

### MODULE 3: Μηχανή Σχεδίασης Sprite & Dual Pistol Bullet Pool

#### Στόχος
Ρουτίνα σχεδίασης sprite 8 bytes × 48 γραμμές με transparency masking και σύστημα διαχείρισης των 2 όπλων (14 σφαίρες) με ανεξάρτητα fire states.

#### Prompt προς το AI
```markdown
Γράψε σε Z80 Assembly (συμβατό με RASM) για τον Amstrad CPC 6128:

1. Ρουτίνα σχεδίασης Sprite με Μάσκα:
   - Διαστάσεις: 8 bytes πλάτος x 48 γραμμές ύψος.
   - Είσοδος: HL = Διεύθυνση Sprite Data/Mask, DE = Screen Memory Address.
   - Λειτουργία: Χρησιμοποίησε γρήγορο masking:
       `SCREEN_BYTE = (SCREEN_BYTE AND MASK_BYTE) OR SPRITE_BYTE`
   - Υπολογισμός επόμενης γραμμής σάρωσης CPC (προσθήκη &0800, και χειρισμός ορίου 8 γραμμών με προσθήκη &C050).
   - Διατήρηση registers: Ελαχιστοποίηση push/pop, χρήση shadow registers (EXX) αν απαιτείται για ταχύτητα.

2. Σύστημα Dual Pistols & Bullet Pool:
   - Δομή δεδομένων για 14 σφαίρες (Active, X, Y, Direction, Life).
   - Μεταβλητές:
     * `MAG_LEFT`: 0-7
     * `MAG_RIGHT`: 0-7
     * `ACTIVE_GUN`: 0 = Left, 1 = Right
     * `RELOAD_TIMER`: bytes καθυστέρησης reload
   - Ρουτίνα `FIRE_BULLET`:
     * Ελέγχει αν το ενεργό όπλο έχει σφαίρες.
     * Εναλλάσσει το `ACTIVE_GUN` (0 -> 1 -> 0).
     * Αν και τα δύο έχουν 0, εκκινεί `RELOAD_TIMER`.
   - Ρουτίνα `UPDATE_BULLETS`:
     * Μετακινεί ενεργές σφαίρες κατά 4 pixels/frame.
     * Ελέγχει collision με το tilemap (αν χτυπήσει solid tile, σβήνει).

Δώσε τον πλήρη κώδικα με ανάλυση κύκλων T-states στις κρίσιμες λούπες.
```

---

### MODULE 4: Υβριδική Μηχανή Scrolling (Horizontal & Vertical)

#### Στόχος
Υλοποίηση των δύο διαφορετικών τρόπων κίνησης της οθόνης: Horizontal scrolling για Πόλη/Δάσος/Έρημο/Σταθμό και Vertical scrolling (Ανάβαση για Σπηλιά, Κάθοδος/Βύθιση για Υποθαλάσσιο).

#### Prompt προς το AI
```markdown
Σχεδίασε τη μηχανή Tilemap και Scrolling για τον CPC 6128 σε Mode 0:

1. Tilemap Specs:
   - Tiles: 16x16 pixels (8 bytes x 16 γραμμές).
   - Map buffer αποθηκευμένο σε Extended RAM bank.

2. Horizontal Scrolling Engine (Επίπεδα 1, 2, 5, 6):
   - Χρήση του Hardware Scroll του CRTC (Registers 12 & 13) για coarse scrolling ανά 2 bytes (4 pixels Mode 0).
   - Ρουτίνα ανανέωσης της νέας κολόνας tiles στην άκρη της οθόνης κατά την κύλιση.

3. Vertical Scrolling Engine:
   - Λειτουργία Ανάβασης (Επίπεδο 3 - Σπηλιά): Scrolling από κάτω προς τα πάνω. Κάθε φορά που η Kara ανεβαίνει, η οθόνη κυλά προς τα κάτω αποκαλύπτοντας τα ψηλότερα επίπεδα.
   - Λειτουργία Κατάδυσης (Επίπεδο 4 - Υποθαλάσσιο): Scrolling από πάνω προς τα κάτω. Φυσική μειωμένης βαρύτητας (άνωση), συνεχής έλξη προς τα πάνω εκτός αν η Kara κολυμπά προς τα κάτω.
   - Υπολογισμός CRTC Start Address για Vertical Roll χωρίς tearing (συγχρονισμός με VBLANK / HALT).

Δώσε τον Z80 κώδικα για τον υπολογισμό των δεικτών VRAM και τη διαχείριση του seamless wrap-around.
```

---

### MODULE 5: Αντικείμενα, Γρίφοι & Interaction Matrix

#### Στόχος
Υλοποίηση του συστήματος καταστάσεων παιχνιδιού: απογραφή αντικειμένων (Inventory), αλληλεπίδραση με πόρτες, εξώφυλλα βιβλίων, βάσεις αγαλμάτων, NPCs και διαχείριση ενέργειας/φαρμακείων.

#### Prompt προς το AI
```markdown
Γράψε το σύστημα λογικής αντικειμένων και γρίφων (Inventory & Interactions) σε Z80 Assembly:

1. Game State Structure:
   ```asm
   PLAYER_HP:        DB 100
   KEYS_COUNT:       DB 0
   COINS_COUNT:      DB 0
   AMMO_RESERVE:     DB 28
   STATUES_HELD:     DB 0
   CURRENT_BOOK_ID:  DB 0
   ```

2. Interaction Handlers:
   - `CHECK_KEY_DOOR`: Έλεγχος επαφής Kara με tile πόρτας. Αν `KEYS_COUNT > 0`, μείωσε κατά 1, παίξε sound trigger και αντικατάστησε το solid tile πόρτας με walkable background tiles.
   - `PLACE_STATUE`: Αν η Kara βρίσκεται σε tile "Altar/Base" και `STATUES_HELD > 0`, τοποθέτησε το άγαλμα, μηδένισε το flag και άλλαξε το status των παγίδων του τρέχοντος δωματίου σε INACTIVE.
   - `READ_BOOK_PUZZLE`: Εμφάνιση pop-up mini interface 3 συμβόλων. Έλεγχος εισόδου παίκτη με αποθηκευμένο συνδυασμό πόρτας.
   - `TALK_NPC_COIN`: Έλεγχος εγγύτητας με NPC. Αν πατηθεί UP και `COINS_COUNT > 0`, μείωση νομίσματος και εμφάνιση κυλιόμενου μηνύματος κειμένου (Hint String).
   - `USE_MEDKIT`: Αύξηση `PLAYER_HP` κατά 35 (max cap 100).

3. Routine `ENTITY_COLLISION_CHECK`:
   - Axis-Aligned Bounding Box (AABB) έλεγχος μεταξύ Kara και διαδραστικών pickups.

Δώσε τη δομή μνήμης και τον πλήρη κώδικα διαχείρισης συμβάντων.
```

---

### MODULE 6: Μηχανή Μεταβάσεων & Διαχείριση Cutscenes

#### Στόχος
Ομαλή ροή μεταξύ των 6 πιστών με μικρά ενδιάμεσα cutscenes και εναλλαγές παλέτας/interrupts.

#### Prompt προς το AI
```markdown
Σχεδίασε τη μηχανή State Transitions (FSM) για τις μεταβάσεις των επιπέδων:

1. Level Flow Manager:
   - Κατάσταση `STATE_LEVEL_PLAY` -> `STATE_LEVEL_CLEAR` -> `STATE_CUTSCENE` -> `STATE_LOAD_NEXT`.

2. Cutscenes Logic:
   - Μετάβαση 1 -> 2: Scripted sprite αυτοκινήτου που διασχίζει την οθόνη προς τα δεξιά, σταδιακό Fade out σε μαύρο.
   - Μετάβαση 2 -> 3: Η Kara μπαίνει σε μαύρο άνοιγμα σπηλαίου. Switch video mode offsets από Horizontal σε Vertical.
   - Μετάβαση 3 -> 4: Water rising effect: Χρήση Raster Interrupts (CRTC scanline interrupts) για σταδιακή αλλαγή της παλέτας από κάτω προς τα πάνω σε αποχρώσεις μπλε/κυανού.
   - Μετάβαση 4 -> 5: Cutscene καταρράκτη που ρέει σε άμμο όασης.
   - Μετάβαση 5 -> 6: Sprite πυραύλου που κινείται κατακόρυφα με particle exhaust (stochastic noise bytes) και μετάβαση στο Space Station bank.

3. Palette Fading Engine:
   - Ρουτίνα απαλού Fade to Black και Fade In μέσω του Gate Array (`&7F00` + Pen Index).

Γράψε τις ρουτίνες Z80 και τη λογική scheduling των cutscenes.
```

---

### MODULE 7: Ήχος 3 Καναλιών (AY-3-8912) & Python Converter Pipeline

#### Στόχος
Πλήρες pipeline για μουσική 3 καναλιών και ηχητικά εφέ με προτεραιότητα (SFX override) στο chip AY-3-8912 του CPC.

#### Prompt προς το AI
```markdown
Χρειαζόμαστε την υλοποίηση του συστήματος ήχου για το PSG AY-3-8912:

1. Python Audio Tool (`audio_pipeline.py`):
   - Χρησιμοποιεί `ffmpeg` για ανάλυση audio/MIDI stems.
   - Διαχωρίζει τη μουσική σε 3 μονοφωνικά κανάλια:
     * Channel A: Lead Synth / Melody
     * Channel B: Bassline / Counterpoint
     * Channel C: Rhythm / Arpeggios / SFX Carrier
   - Εξάγει binary αρχείο κατάλληλο για Arkos Tracker 2 (AKG format) ή custom lightweight tracker player.

2. Z80 Sound Engine & SFX Priority Manager:
   - Ενσωμάτωση του player στην Interrupt ρουτίνα (50 Hz / VBLANK).
   - Σύστημα SFX Priority:
     * Όταν πυροβολεί το πιστόλι (`SFX_GUNSHOT`) ή χτυπιέται η Kara (`SFX_HURT`), το Κανάλι C αποσυνδέεται προσωρινά από τη μουσική.
     * Παίζει το SFX χρησιμοποιώντας το Hardware Noise Generator (Reg 6) και Volume Envelope (Reg 8-10).
     * Μόλις ολοκληρωθεί το εφέ, το Κανάλι C επιστρέφει απρόσκοπτα στην αναπαραγωγή της μουσικής.

Δώσε το Python script και τον Z80 wrapper του SFX player.
```

---

## 6. Checklist Ελέγχου Ποιότητας & Οδηγίες Αποσφαλμάτωσης

Πριν θεωρηθεί έτοιμο κάθε module, πρέπει να επαληθεύονται τα εξής:

1. **Κύκλοι T-States και VBLANK:**
   * Η σχεδίαση της Kara Loft (48x16) μαζί με αποκατάσταση φόντου και 14 σφαίρες δεν πρέπει να υπερβαίνει τα 19.968 T-states (1 frame στα 50 Hz = 80.000 T-states, αφήνοντας 75% CPU για scrolling και λογική).
2. **Crash Prevention στο Bank Switching:**
   * Ποτέ μην εκτελείς κώδικα μέσα από το memory range `&4000 - &7FFF` τη στιγμή που αλλάζεις το Bank μέσω του Gate Array. Ο κώδικας switching πρέπει να βρίσκεται πάντα στην Base RAM (`&0000 - &3FFF` ή `&8000 - &BFFF`).
3. **CRTC Type Compatibility:**
   * Το overscan (192×272) και το hardware scrolling πρέπει να δοκιμάζονται σε CRTC Type 0, 1, 2 και 4 (δοκιμή σε RetroVirtualMachine και Caprice32).
4. **Στοίβα (Stack):**
   * Ο SP πρέπει να αρχικοποιείται ρητά (`LD SP, &BFFF`) ώστε να μην εισχωρήσει ποτέ στη VRAM (`&C000 - &FFFF`) προκαλώντας visual glitches.

---

## 7. Συνοπτικός Οδηγός Εκκίνησης (Quick Start)

1. Φτιάξε φάκελο έργου: `mkdir kara_loft && cd kara_loft`.
2. Αντέγραψε το **MODULE 1 Prompt** στο AI.
3. Πάρε τον κώδικα, τρέξε το build script και βεβαιώσου ότι δημιουργείται το `kara.dsk` και εκτελείται στον emulator.
4. Προχώρησε στο **MODULE 2** για τη δημιουργία των graphic assets.
5. Συνέχισε γραμμικά μέχρι το **MODULE 7**.
