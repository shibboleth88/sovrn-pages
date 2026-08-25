/* Shared by exhibitions.html, collections.html and museums-overview.html.
   One list, three pages: add a show here and all three pick it up.
   Row: [url, place, title, meta, blurb, image, pad?, upcoming?]
   image: a bare filename resolves against B; anything with a slash is used as-is. */
const B="https://raw.githubusercontent.com/gorgonorgon/museum-photos/main/";
const EX=[
["https://www.sovrn.art/exhibitions/fc-3-blockchains","Francisco Carolinum, Linz","Collection Francisco Carolinum — 3 Blockchains, one Collection","9 Sep 2026 – 7 Feb 2027",
"The museum’s blockchain collection shown across Ethereum, Tezos and Bitcoin, curated by Julia Staudach. Eight of the Sovrn set’s ten artists are on the roster.",
"img/pages/overview/fc-3-blockchains.jpg",0,1],
["https://www.sovrn.art/exhibitions/screens-contextualized","NEORT, Shibuya","SCREENS CONTEXTUALIZED","9 – 22 Feb 2026",
"Two Mobility works by bashobits across Shibuya’s public signage, including Aura Afterglow at Miyashita Park for the Weather Writes open call.",
"img/pages/overview/screens.jpg"],
["https://www.sovrn.art/exhibitions/ucca","UCCA, Beijing","Rutherford Chang: Hundreds and Thousands","17 Jan – 12 Apr 2026",
"CENTS shown in the first institutional survey of Chang’s work, co-curated by Philip Tinari and Aki Sasamoto with the artist’s estate.",
"img/pages/overview/ucca.webp"],
["https://www.sovrn.art/exhibitions/marfa-popup","Sovrn, Marfa, Texas","A sovrn Pop-Up Gallery","16 – 19 Oct 2025",
"Nine curated collections shown from the cloudpainter truck during Art Blocks Marfa Weekend, with prints signed on the spot by the robot.",
"img/pages/overview/marfa.jpg"],
["https://www.sovrn.art/exhibitions/bankable","Arab Bank Switzerland, Basel","BANKABLE","15 – 21 Jun 2025",
"CENTS shown in the Arab Bank Switzerland room at Basel Social Club during Art Basel, curated by Nina Roehrs. The coins were struck in 1971.",
"img/pages/overview/bankable.jpg"],
["https://www.sovrn.art/exhibitions/christies-augmented-intelligence","Christie’s, New York","Augmented Intelligence","20 Feb – 5 Mar 2025",
"Nine canvases from Emerging Faces in the first sale a major auction house devoted entirely to art made with AI.",
"img/pages/overview/christies.jpg",1],
["https://www.sovrn.art/exhibitions/vitra","Vitra Design Museum","Science Fiction Design: From Space Age to Metaverse","18 May 2024 – 10 May 2026",
"Twenty-one works from Latent Couture by Mikey Woodbridge, among the contemporary futurisms closing a two-year exhibition.",
"img/pages/overview/vitra.webp"],
["https://www.sovrn.art/exhibitions/kindl","KINDL, Berlin","POLY. A Fluid Show","17 Sep 2023 – 25 Feb 2024",
"Latent Couture as a wall-scale printed grid, with Mikey Woodbridge performing at the opening and the finissage.",
"img/pages/overview/kindl.jpeg"]];
const CO=[
["https://www.sovrn.art/museums/fransisco-carolinum","Francisco Carolinum, Linz","Sovrn Full Set","Eleven works on Ethereum · 2022–2025",
"A complete set, one work from every Sovrn collection on Ethereum, in the permanent collection of the museum for photography and media art of Upper Austria.",
"img/pages/overview/fc-collection.jpg"],
["https://www.sovrn.art/museums/moca","Museum of Crypto Art","Five Reflections","Five works · Pindar Van Arman",
"Five works from Reflection, Van Arman’s fully on-chain execution of his reflective AI process, in MOCA’s permanent collection.",
"img/pages/overview/moca.png",1],
["https://www.sovrn.art/collections/abs-collection","Arab Bank Switzerland","Sightseers 104","One work · Norman Harman",
"One of the five hundred SIGHTSEERS, in the bank’s digital art collection alongside OPERATOR, Entangled Others and Anna Lucia.",
"img/pages/overview/arab-bank.jpg"],
["https://www.sovrn.art/museums/lacma","LACMA, Los Angeles","AI Imagined Portrait Painted by a Robot #2","One work · Pindar Van Arman",
"A 2018 robotic painting, donated by Cozomo de’ Medici among the first blockchain-minted works to enter an American art museum.",
"img/pages/overview/lacma.jpeg"]];
