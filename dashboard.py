import gradio as gr

from recommender import BookRecommender

recommender = BookRecommender.load()


def format_results(recommendations):
    """
    Turn a recommendations DataFrame into (thumbnail, caption) tuples for the gallery.
    """
    results = []

    for _, row in recommendations.iterrows():
        # some books have missing (NaN, a float) description/authors -> coerce to safe strings
        description = row["description"] if isinstance(row["description"], str) else ""
        truncated_desc_split = description.split()
        truncated_description = " ".join(truncated_desc_split[:30]) + "..."

        authors = row["authors"] if isinstance(row["authors"], str) else "Unknown author"

        # if a book has 2 authors use "and" if more use commas and a final "and"
        authors_split = authors.split(";")
        if len(authors_split) == 2:
            authors_str = f"{authors_split[0]} and {authors_split[1]}"
        elif len(authors_split) > 2:
            authors_str = f"{', '.join(authors_split[:-1])}, and {authors_split[-1]}"
        else:
            authors_str = authors

        caption = f"{row['title']} by {authors_str}: {truncated_description}"
        results.append((row["large_thumbnail"], caption))

    return results


def recommend_books(query: str, category: str, tone: str):
    return format_results(recommender.recommend_from_query(query, category, tone))


def recommend_from_selection(book1, book2, book3):
    return format_results(recommender.recommend_from_books([book1, book2, book3]))


categories = recommender.categories
tones = ["All"] + ["Happy", "Surprising", "Angry", "Suspenseful", "Sad"]
book_choices = recommender.book_choices

# keep the long "Title by Author" text from sliding under the dropdown's chevron
css = """
.book-picker input { padding-right: 2.2rem !important; text-overflow: ellipsis; }
"""

with gr.Blocks(theme=gr.themes.Base(), css=css) as dashboard:
    gr.Markdown("# Semantic book recommender")

    with gr.Tab("Search by description"):
        with gr.Row():
            user_query = gr.Textbox(label = "Please enter a description of a book:",
                                    placeholder = "e.g., A story about forgiveness", scale=2)
            category_dropdown = gr.Dropdown(choices = categories, label = "Select a category:", value = "All", scale=1)
            tone_dropdown = gr.Dropdown(choices = tones, label = "Select an emotional tone:", value = "All", scale=1)
            submit_button = gr.Button("Find recommendations", variant="primary", scale=1)

        gr.Examples(
            examples = ["A book to teach children about nature",
                        "A story about forgiveness",
                        "A thrilling space adventure",
                        "An uplifting memoir about overcoming adversity"],
            inputs = user_query,
        )

        gr.Markdown("## Recommendations")
        output = gr.Gallery(label="Recommended books", columns=5, rows=2, height="auto", object_fit="contain")

        #trigger on both the button click and pressing Enter in the textbox
        search_inputs = [user_query, category_dropdown, tone_dropdown]
        submit_button.click(fn = recommend_books, inputs = search_inputs, outputs = output)
        user_query.submit(fn = recommend_books, inputs = search_inputs, outputs = output)

    with gr.Tab("Find by three books"):
        gr.Markdown("Pick three books you like and get a recommendation in the same vein.")
        with gr.Row():
            book1_dropdown = gr.Dropdown(choices=book_choices, label="Book 1", elem_classes="book-picker")
            book2_dropdown = gr.Dropdown(choices=book_choices, label="Book 2", elem_classes="book-picker")
            book3_dropdown = gr.Dropdown(choices=book_choices, label="Book 3", elem_classes="book-picker")
        find_button = gr.Button("Find a book based on these", variant="primary")

        gr.Markdown("## Recommendations")
        selection_output = gr.Gallery(label="Recommended books", columns=8, rows=2)

        find_button.click(fn = recommend_from_selection,
                          inputs = [book1_dropdown, book2_dropdown, book3_dropdown],
                          outputs = selection_output)


if __name__ == "__main__":
    dashboard.launch()
