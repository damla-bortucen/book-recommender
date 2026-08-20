""" Evaluation cases: a query and the book it should return.

Queries are written the way someone would actually search — plot and theme, not
the publisher's blurb. Deliberately avoid words from the title: the embedded
text is `title\\nauthors\\ndescription`, so a title word in the query leaks the
answer and the case stops testing anything.

Titles resolve through search_titles (ILIKE, most-read first), so a short
unambiguous fragment is enough — "Educated" finds "Educated: A Memoir".
Mind the apostrophes: several titles use a curly ’ rather than ', so prefer a
fragment without one ("Handmaid").
"""

CASES = [
    # --- easy (should rank 1) ---
    ("a desert planet, warring noble houses, and a boy who becomes a messiah", "Dune"),
    ("a girl falls down a rabbit hole into a whimsical world and has adventures", "Alice's Adventures in Wonderland"),
    ("a young wizard discovers he's famous and goes to a school for magic", "Harry Potter and the Philosopher's Stone"),
    ("whales, obsession, and a captain hunting the creature that maimed him", "Moby Dick"),
    ("a dystopia where books are burned by firemen", "Fahrenheit 451"),
    ("an all-powerful government uses total surveillance and constant propaganda to control citizens", "1984"),
    ("a teenager from a poor district is selected to compete against others in a televised game to the death", "The Hunger Games"),
    ("schoolboys stranded on an island slowly descend into savagery", "Lord of the Flies"),
    ("a comfortable homebody is dragged along on a quest to reclaim treasure from a dragon", "The Hobbit"),
    ("a scientist assembles a creature from corpses and then abandons his creation", "Frankenstein"),
    ("cloned dinosaurs break loose on an island theme park", "Jurassic Park"),
    ("an astronaut is left behind on Mars and grows potatoes to stay alive", "The Martian"),
    ("a boy adrift on a lifeboat with a Bengal tiger", "Life of Pi"),
    ("a pig is saved from slaughter by a spider who writes words in her web", "Charlotte's Web"),
    ("a theocracy forces fertile women to bear children for the ruling class", "Handmaid"),
    ("a man wakes as an insect and his family slowly turns against him", "The Metamorphosis"),
    ("a lone astronaut wakes with amnesia on a mission to save the dying sun", "Project Hail Mary"),
    ("a solicitor visits a Transylvanian count, told through letters and diaries", "Dracula"),

    # --- medium ---
    ("a mysterious millionaire throws lavish parties hoping to win back a lost love", "The Great Gatsby"),
    ("citizens are bred into castes and kept docile by a happiness drug", "Brave New World"),
    ("a cynical teenager wanders the city after being expelled from school", "The Catcher in the Rye"),
    ("a wife vanishes on her wedding anniversary and her husband becomes the suspect", "Gone Girl"),
    ("a girl raised alone in the marshes becomes a murder suspect", "Where the Crawdads Sing"),
    ("a symbologist chases clues about a religious conspiracy across Europe", "The Da Vinci Code"),
    ("a brilliant, unconventional punk hacker with a troubled past teams up with a disgraced journalist to reopen a disappearance from decades ago", "The Girl with the Dragon Tattoo"),
    ("a father and son push a cart through a burned, ashen country", "The Road"),
    ("a young bride is haunted by the memory of her husband's first wife", "Rebecca"),
    ("a close-knit clique of classics students at a New England college, and a killing", "The Secret History"),
    ("a man lives alone in an endless house of statues and tides, keeping careful journals", "Piranesi"),
    ("five sisters in Regency England and a wealthy, aloof gentleman", "Pride and Prejudice"),

    # --- hard ---
    ("boarding school children slowly discover the terrible purpose they were raised for", "Never Let Me Go"),
    ("an artificial friend in a shop window watches the family who buy her", "Klara and the Sun"),
    ("a travelling troupe performs Shakespeare after a flu pandemic collapses civilisation", "Station Eleven"),
    ("a formerly enslaved woman is haunted by the ghost of her dead daughter", "Beloved"),
    ("two boys in Kabul, a betrayal, and a chance at redemption decades later", "The Kite Runner"),
    ("a young girl in Nazi Germany hides a Jewish man, narrated by Death", "The Book Thief"),
    ("four college friends in New York and one man's unbearable past", "A Little Life"),
    ("two Irish teenagers drift in and out of each other's lives over several years", "Normal People"),
    ("a retelling of the Trojan war as a love story between two men", "The Song of Achilles"),
    ("a child's perspective as her father defends a falsely accused Black man in court", "To Kill A Mockingbird"),

    # --- non-fiction ---
    ("a memoir of growing up in a survivalist family with no schooling, then reaching university", "Educated"),
    ("a sweeping account of how humans came to dominate the planet", "Sapiens"),
    ("how tiny incremental changes to daily routines compound over time", "Atomic Habits"),
    ("two systems of thought and the cognitive biases they produce", "Thinking, Fast and Slow"),
    ("advice on how to be more persuasive and effective through communication and boost happiness", "How to Win Friends and Influence People"),
]