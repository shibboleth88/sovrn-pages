/* The curated collections — the one list, shared by the homepage and /curated.
   It used to live only in home.html, and /curated was a Google Sites page that
   restated it by hand; keeping two copies of fifteen collections is how they end
   up disagreeing about which fifteen. Order is the site's own and is deliberate.

   Each row: [title, artist, url, image, blurb]. */
const H="https://raw.githubusercontent.com/gorgonorgon/images-for-homepage/main/",
F="https://raw.githubusercontent.com/gorgonorgon/sovrn-FC-images/main/",
P="https://raw.githubusercontent.com/gorgonorgon/images-for-homepage/abd8a9f041622904ed28ad947c47b9242d11c2f8/",
S="/curated/";

const C=[
["CENTS","Rutherford Chang","/cents",H+"cent_homepage.jpg","The performance of value"],
["Emerging Faces","Pindar Van Arman","https://www.vanarman.com/emergence",H+"emerging-faces.jpg","The first robotic paintings autonomously created from neural networks (2017)."],
["Reflection","Pindar Van Arman",S+"reflection",F+"reflection_889_layers_smooth.svg","Van Arman’s Reflective AI process, executed fully on-chain"],
["Wunderkammer","Isa Kost",S+"wunderkammer",H+"wunderkammer_homepage.gif","An on-chain Cabinet of Wonders, to give eternal life to the dead presences that Isa Kost has carried through the years — every object a dead memory that has called out to be found."],
["Painting with Fire: a history in GANs","Bård Ionson",S+"painting-with-fire",H+"fire_homepage.jpg","The evolution of GANs from 2014 to 2023, seen through the eyes of fire. Fourteen vintage models and two hundred works, each invoking the same elemental image."],
["Noctilucent Mementi","Martin Lukas Ostachowski / MLO.art",S+"mementi",H+"mementi_homepage.jpg","A generative chronicle of five years of travel and work with clouds. In the artist’s words: noctilucent clouds are invisible memories, glowing when revisited."],
["Possibility Spaces","Look Highward",S+"possibility-spaces",H+"possibility_spaces_homepage.jpg","Stunningly vast worlds extending over 250 million pixels, evolved through an emergent series of calls and responses between artist and AI: spiritual experience seen through the mind’s eye of machine learning."],
["Sightseers: Perimeter Town","Norman Harman",S+"perimeter-town",H+"perimeter_town_homepage.jpg","Harman strays out further from the motel to pluck the outgrowths of the glitched and morphic wastelands: the refined emergences on the perimeter of the SIGHTSEERS world."],
["Seasons of Mobility","bashobits",S+"seasons-of-mobility",H+"seasons-of-mobility.jpg","It is the year 1010 After Humanity. We are long gone, but life continues — the autonomous trains, buses and cars we created have become a new species that calls itself Mobility."],
["Latent Couture","Mikey Woodbridge",S+"latent-couture",H+"latent_couture_homepage.jpg","555 fashion statements trained on Woodbridge’s years as performer, painter, designer and nightlife icon. The opposite of a deepfake. Each piece says, “This person is possible.”"],
["byteGANs","Pindar Van Arman",S+"bytegans",H+"bytegan 842.svg","The first fully on-chain AI art collection on Ethereum. A kilobyte on the ledger, dancing forever dances."],
["RABBIT TAKEOVER","Anne Spalter",S+"rabbit-takeover",H+"rabbit_takeover_homepage.jpg","A lone rabbit cavorting about in a post-armageddon world, travelling through swirling trans-dimensional portals to preside over scenes of mayhem and destruction. Based on Spalter’s pet, Pickles."],
["SIGHTSEERS","Norman Harman",S+"sightseers",H+"sightseers_homepage.jpg","Harman masterfully mixes painting, glitch art, and AI to build a world based on the sightseers who came to watch the nuclear bomb tests outside Las Vegas."],
["cope. Vol 1","aleqth",S+"cope-vol-1",P+"cope-vol-1.jpg","A book made and self-published in October 2021, its pages created day by day and the making live-shared page by page. Each page, and both covers, tokenized on the blockchain."],
["AI Spaceships","Anne Spalter",S+"ai-spaceships",H+"ai-spaceships.jpg","Climate change has made Earth uninhabitable and the remaining people build ships to leave. Some fail at launch and go down in flames; others warp to steampunk battleships, or to neon hyperspace."]];
