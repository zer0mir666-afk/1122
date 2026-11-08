const categoryGroups = [
  {
    title: 'Одежда',
    items: [
      'Куртки', 'Зимние куртки', 'Пальто и плащи', 'Жилеты', 'Рубашки',
      'Футболки', 'Поло', 'Толстовки', 'Свитеры и кардиганы', 'Джинсы',
      'Брюки',
    ],
  },
  {
    title: 'Обувь',
    items: [
      'Кроссовки', 'Кеды', 'Классическая обувь', 'Ботинки', 'Летняя обувь',
    ],
  },
  {
    title: 'Сумки и багаж',
    items: [
      'Сумки', 'Рюкзаки', 'Дорожные сумки', 'Чемоданы',
    ],
  },
  {
    title: 'Аксессуары',
    items: [
      'Ремни', 'Головные уборы', 'Шарфы', 'Перчатки', 'Галстуки и платки',
      'Кошельки и кардхолдеры', 'Очки', 'Часы', 'Украшения', 'Запонки',
    ],
  },
];

const storageKey = 'atelier-catalog-category-selection-v4';
const groupRoot = document.querySelector('#category-groups');
const searchInput = document.querySelector('#category-search');
const countElement = document.querySelector('#selection-count');
const copyButton = document.querySelector('#copy-selection');
const resetButton = document.querySelector('#reset-selection');
const emptySearch = document.querySelector('#empty-search');
const toast = document.querySelector('#toast');

function categoryId(groupTitle, item) {
  return `${groupTitle}::${item}`;
}

function readSelection() {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || '[]');
    return new Set(Array.isArray(stored) ? stored : []);
  } catch {
    return new Set();
  }
}

const selected = readSelection();

function renderGroups() {
  groupRoot.innerHTML = categoryGroups.map((group, groupIndex) => `
    <section class="category-group" data-group="${groupIndex}">
      <div class="group-heading">
        <h2>${group.title}</h2>
        <span class="group-count" data-group-count="${groupIndex}">0 из ${group.items.length}</span>
      </div>
      <div class="option-grid">
        ${group.items.map((item, itemIndex) => {
          const id = categoryId(group.title, item);
          return `
            <label class="category-option" data-search-value="${item.toLowerCase()}" data-item="${itemIndex}">
              <input type="checkbox" value="${id}" ${selected.has(id) ? 'checked' : ''} />
              <span class="checkmark" aria-hidden="true"></span>
              <span class="option-name">${item}</span>
            </label>`;
        }).join('')}
      </div>
    </section>`).join('');
}

function saveSelection() {
  localStorage.setItem(storageKey, JSON.stringify([...selected]));
}

function updateCounts() {
  document.querySelectorAll('.category-group').forEach((section) => {
    const groupIndex = Number(section.dataset.group);
    const checked = section.querySelectorAll('input:checked').length;
    section.querySelector('[data-group-count]').textContent = `${checked} из ${categoryGroups[groupIndex].items.length}`;
  });
  countElement.textContent = selected.size;
  copyButton.disabled = selected.size === 0;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 1500);
}

function selectedText() {
  const lines = ['Выбранные категории каталога:', ''];
  categoryGroups.forEach((group) => {
    const chosen = group.items.filter((item) => selected.has(categoryId(group.title, item)));
    if (!chosen.length) return;
    lines.push(group.title);
    chosen.forEach((item) => lines.push(`- [x] ${item}`));
    lines.push('');
  });
  return lines.join('\n').trim();
}

async function copySelection() {
  const text = selectedText();
  try {
    await navigator.clipboard.writeText(text);
    showToast('Список скопирован');
  } catch {
    const field = document.createElement('textarea');
    field.value = text;
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.appendChild(field);
    field.select();
    document.execCommand('copy');
    field.remove();
    showToast('Список скопирован');
  }
}

function filterCategories() {
  const query = searchInput.value.trim().toLowerCase();
  let visibleOptions = 0;
  document.querySelectorAll('.category-group').forEach((section) => {
    let groupVisible = 0;
    section.querySelectorAll('.category-option').forEach((option) => {
      const visible = !query || option.dataset.searchValue.includes(query);
      option.hidden = !visible;
      if (visible) groupVisible += 1;
    });
    section.hidden = groupVisible === 0;
    visibleOptions += groupVisible;
  });
  emptySearch.hidden = visibleOptions !== 0;
}

groupRoot.addEventListener('change', (event) => {
  const checkbox = event.target.closest('input[type="checkbox"]');
  if (!checkbox) return;
  if (checkbox.checked) selected.add(checkbox.value);
  else selected.delete(checkbox.value);
  saveSelection();
  updateCounts();
});

searchInput.addEventListener('input', filterCategories);
copyButton.addEventListener('click', copySelection);
resetButton.addEventListener('click', () => {
  if (!selected.size) return;
  selected.clear();
  document.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = false;
  });
  saveSelection();
  updateCounts();
  showToast('Выбор очищен');
});

renderGroups();
updateCounts();
