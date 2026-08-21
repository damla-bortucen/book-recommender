const booksForm = document.getElementById('books-form');
const chips = document.getElementById('chips');
const bookInput = document.getElementById('book-q');
const pickCount = document.getElementById('pick-count');

document.getElementById('book-options').addEventListener('click', function (e) {
    const opt = e.target.closest('.option');
    if (opt) addPick(opt.dataset.id, opt.dataset.label);
});

function updateFeedback() {
    const n = booksForm.querySelectorAll('input[name="picks"]').length;
    pickCount.textContent = n + ' / 3 selected';
    bookInput.disabled = n >= 3; // disable the box at the limit
}

function addPick(bookId, label) {
    const picks = booksForm.querySelectorAll('input[name="picks"]');
    if (picks.length >= 3) return;                                                   // max 3
    if (booksForm.querySelector('input[name="picks"][value="' + bookId + '"]')) return; // no dupes

    // hidden field that actually gets submitted
    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'picks';
    hidden.value = bookId;
    booksForm.appendChild(hidden);

    // visible chip
    const chip = document.createElement('span');
    chip.className = 'chip';

    const text = document.createElement('span');
    text.textContent = label;
    chip.appendChild(text);

    // the remove (×) button
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
    remove.className = 'chip-remove';
    
    remove.addEventListener('click', function () {
        hidden.remove();      // stop it being submitted
        chip.remove();        // remove the visible chip
        updateFeedback();     // and let the counter and the input catch up
    });
    chip.appendChild(remove);

    chips.appendChild(chip);
    updateFeedback();
    closeOptions();
}

const tabButtons = document.querySelectorAll('.tab-btn');
const panels = {
    search: document.getElementById('panel-search'),
    books: document.getElementById('panel-books'),
};

// Emptying it is what hides it: #book-options:not(:has(*)) is display:none.
function closeOptions() {
    document.getElementById('book-options').innerHTML = '';
}

document.addEventListener('click', function (e) {
    if (!e.target.closest('#panel-books')) closeOptions();
});

tabButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
        const target = btn.dataset.tab;

        panels.search.classList.toggle('hidden', target !== 'search');  // hide non-active
        panels.books.classList.toggle('hidden', target !== 'books');

        tabButtons.forEach(function (b) {
            const active = b.dataset.tab === target;
            b.classList.toggle('is-active', active);      // CSS decides what active looks like
            b.setAttribute('aria-selected', active);
        });
    });
});

function closeModal() {
    document.getElementById('modal').innerHTML = '';
}

document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeModal();
});