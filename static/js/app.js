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
    chip.className = 'inline-flex items-center gap-1 rounded-full bg-sky-100 px-3 py-1 text-sm text-sky-800';

    const text = document.createElement('span');
    text.textContent = label;
    chip.appendChild(text);

    // the remove (×) button
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
    remove.className = 'font-bold leading-none text-sky-500 hover:text-sky-800';
    remove.addEventListener('click', function () {
    hidden.remove();   // stop it being submitted
    chip.remove();     // remove the visible chip
    });
    chip.appendChild(remove);
    updateFeedback();

    chips.appendChild(chip);
    updateFeedback();
}

const tabButtons = document.querySelectorAll('.tab-btn');
const panels = {
    search: document.getElementById('panel-search'),
    books: document.getElementById('panel-books'),
};

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