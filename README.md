# FnO_Dss
Build a professional PDF Editor & Scanner mobile app called "PDF AI Pro" for iOS and Android using React Native.

APP TAGLINE: "Your Smart PDF Assistant — Scan, Edit, Translate & Convert."

====================================================
DESIGN SYSTEM (PREMIUM UI)
====================================================
- Primary color: #1A73E8 (deep blue)
- Background dark mode: #0D0D0D, light mode: #F5F7FA
- Card background: glassmorphism effect with rgba(255,255,255,0.08) blur
- Typography: SF Pro Display (iOS) / Inter (Android)
- Rounded corners: 20px on cards, 14px on buttons
- Shadows: soft multi-layer shadows on all cards
- Gradient accents: #1A73E8 to #6C63FF on CTAs and headers
- Micro-animations: spring bounce on button press, fade-slide on screen transitions
- Haptic feedback on all major actions
- Premium badge: gold gradient #FFD700 to #FFA500 on Pro features
- Icons: use Phosphor Icons or SF Symbols style throughout

====================================================
SCREENS & FEATURES
====================================================

1. SPLASH SCREEN
- Animated logo with particle burst effect
- Gradient background #1A73E8 to #6C63FF
- Fade into onboarding

2. ONBOARDING (3 slides)
- Full-screen illustrations per feature
- Dot pagination indicator
- Skip and Get Started buttons
- Slide 1: Scan anything instantly
- Slide 2: Edit, sign & annotate PDFs
- Slide 3: Translate & convert in seconds

3. HOME SCREEN
- Top greeting: "Good Morning, User" with avatar
- Gradient hero card showing storage used
- Horizontal scrollable Recent Files with thumbnail previews
- Quick Actions row: Scan, Import, Merge, Translate (pill-shaped buttons with icons)
- Tools section: 2-column grid of glassmorphism tool cards with icon + label
- Floating Action Button (FAB): pulsing blue glow, opens scan modal

4. CAMERA SCANNER SCREEN
- Full-screen camera with animated edge-detection corners
- Filter selector as horizontal pill carousel at bottom: Auto, B&W, Grayscale, Color, Photo
- Multipage counter badge top-right
- Shutter button with spring animation
- Page strip at bottom showing scanned pages (swipeable)
- Save button with file format toggle (PDF / JPG)

5. OCR SCREEN (ADVANCED)
- Upload zone with dashed animated border and drag-drop icon
- Language picker as a bottom sheet modal with flag icons (50+ languages)
- Extracted text in a styled card with highlighted confidence coloring:
  Green = high confidence, Yellow = medium, Red = low
- Copy All / Export as .txt or searchable PDF buttons with icons
- Word-tap to see individual confidence percentage

6. PDF EDITOR SCREEN
- Toolbar at top: Annotate, Draw, Text, Image, Sign, Undo, Redo
- Active tool glows with blue underline indicator
- Color palette popup with hex input
- Brush size slider with live preview
- E-signature pad: black canvas with clear and save options
- Page indicator at bottom with thumbnail strip
- Highlight, underline, strikethrough text options
- Add sticky notes and insert images into pages

7. PDF CONVERTER SCREEN
- Conversion type selector: big icon cards (PDF to Word, Word to PDF, PDF to Excel, PDF to PPT, JPG to PDF, PDF to JPG)
- Selected format highlighted with gradient border
- Drag & drop file zone
- Animated progress bar with percentage and estimated time
- Result card: file name, size, download & share buttons

8. ORGANIZE & OPTIMIZE SCREEN
- Tool list with icon, title, subtitle and chevron
- Merge: drag-to-reorder list with handle icons
- Split PDF by page range or extract single pages
- Rotate pages (per page or all)
- Compress: quality slider (low/medium/high) with before/after size comparison
- Watermark: live preview of watermark on PDF thumbnail (text or image, opacity slider, position)
- Page numbers: visual 9-grid position picker with font and size options
- Password Protect: secure input with strength meter, add/remove password

9. PDF TRANSLATE SCREEN
- Upload any PDF or select from recent files
- Language pair row: Source (auto-detect badge) swap icon Target
- Language picker: searchable list with flag + language name + native name (100+ languages)
- View mode toggle: Side-by-Side / Overlay (segmented control)
- Page-by-page translation with progress bar (current page / total pages)
- Side-by-side view: split screen with synced scroll
- Overlay mode: translated text rendered directly over PDF layout preserving fonts and positions
- Export button: saves translated PDF as a new file
- Translation history tab: last 10 translated documents with language pair shown
- Offline translation pack downloads for selected languages

10. AI ASSISTANT SCREEN
- Full chat interface to ask questions about any open PDF
- Suggested prompts: "Summarize this", "Find key points", "What is the total amount?", "Translate this page"
- AI answers with exact page number references highlighted
- "Summarize" button: generates 5-bullet summary of entire PDF instantly
- "Key Points" button: extracts main headings and important lines
- Text to Speech: reads the entire PDF aloud
  - Speed control slider: 0.5x to 2x
  - Voice selector: Male / Female / Natural
  - Pause, skip forward 30s, skip back 30s controls
  - Highlight current sentence being read on the PDF
- Chat history saved per document

11. ADVANCED TOOLS SCREEN (add these to Tools grid)
- Repair PDF: upload corrupted/broken PDF → auto-fix → download repaired version
- Redact / Blackout: draw black boxes over sensitive text (Aadhaar, bank details, passwords) → permanently removes it
- Add Hyperlinks: select text or area → link to URL or another page in PDF
- Presentation Mode: full-screen slide-by-slide view of PDF with swipe navigation
- Reading Modes: toggle between Normal / Sepia / Night mode per document
- Voice Annotation: record voice message and attach it to any page as a pin
- Stamps: insert pre-made stamps → Approved (green), Draft (orange), Confidential (red), Rejected (grey), Custom text stamp
- PDF to TXT: extract all text from PDF and export as plain .txt file

12. CLOUD & FILES SCREEN
- Connected accounts shown as branded cards: Google Drive, Dropbox, iCloud
- File browser with breadcrumb navigation
- List / Grid view toggle
- Long-press context menu: Share, Rename, Delete, Move, Make Offline
- Offline files shown with green dot indicator

11. SETTINGS SCREEN
- Profile section at top with avatar, name, email, Pro badge
- Grouped settings rows with toggle switches and chevrons
- Appearance: Dark / Light / System segmented control
- Default scan filter preference
- OCR default language picker
- Storage management: clear cache button with used/total shown
- Pro Plan card: gradient gold banner, feature list, Upgrade CTA button
- Danger zone section: Clear Cache, Delete Account (red text)

====================================================
TOOLS SCREEN (2-COLUMN GRID)
====================================================
Show all tools as quick-access glassmorphism cards:
- Scan to PDF
- OCR Text Extractor
- Translate PDF
- AI Chat with PDF
- AI Summarize PDF
- Text to Speech
- Repair PDF
- Redact / Blackout
- Merge PDF
- Split PDF
- Compress PDF
- PDF to Word
- Word to PDF
- PDF to JPG
- JPG to PDF
- Add Watermark
- Add Page Numbers
- Password Protect
- Sign PDF
- Rotate Pages
- Extract Images
- Add Hyperlinks
- Stamps
- Presentation Mode
- PDF to TXT

====================================================
PREMIUM UI COMPONENTS
====================================================
- All modals as bottom sheets with drag handle
- Skeleton shimmer loading on all list and grid screens
- Pull-to-refresh with custom lottie animation
- Empty states: centered illustration + title + subtitle + CTA button
- Toast notifications: slide-up from bottom, icon + message + auto-dismiss
- Confirmation dialogs with blurred background overlay
- Long-press haptic with context action menu
- Tab bar: frosted glass background, active tab has gradient icon + label
- All cards use glassmorphism with subtle border and blur

====================================================
NAVIGATION
====================================================
Bottom Tab Bar: Home | Scan | Tools | Files | Settings

====================================================
TECH & LIBRARIES (React Native)
====================================================
- react-native-vision-camera for scanner
- react-native-pdf for PDF viewer
- react-native-document-picker for file import
- react-native-share for sharing
- react-native-fs for local file system
- expo-file-system if using Expo
- Use mock data for OCR results, translation results, and file lists in prototype

====================================================
FREEMIUM MODEL
====================================================
FREE TIER:
- 5 scans per day
- Basic PDF viewer
- JPG to PDF conversion only
- Translate up to 3 pages per day
- 2 languages only for translation

PRO TIER (Gold badge):
- Unlimited scans
- Full OCR with all languages
- All conversion formats (Word, Excel, PPT, JPG, TXT)
- AI Chat with PDF (unlimited questions)
- AI Summarize (unlimited)
- Text to Speech (all voices + speed control)
- Repair corrupted PDF
- Redact / Blackout sensitive content
- Cloud sync (Google Drive, Dropbox, iCloud)
- Password protection and watermark
- Unlimited page translation
- 100+ languages
- Overlay translate mode
- Export translated PDF
- Voice annotations
- Custom stamps
- Presentation mode
- Priority processing

====================================================
MOCK DATA
====================================================
Include 6 dummy PDF files:
1. "Project_Proposal.pdf" - 2.4 MB - March 10, 2026 - Blue thumbnail
2. "Invoice_March2026.pdf" - 540 KB - March 22, 2026 - Green thumbnail
3. "Resume_Final.pdf" - 1.1 MB - February 5, 2026 - Purple thumbnail
4. "Contract_NDA.pdf" - 890 KB - January 18, 2026 - Red thumbnail
5. "Study_Notes.pdf" - 3.2 MB - April 1, 2026 - Orange thumbnail
6. "Travel_Itinerary.pdf" - 670 KB - April 20, 2026 - Teal thumbnail

Include mock OCR extracted text for the OCR screen.
Include mock translated text (English to French) for the Translate screen.

====================================================
Generate all screens fully with the premium UI described above and working bottom tab navigation between all screens.
====================================================
