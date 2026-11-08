const root = document.querySelector('#products');

const escapeHtml = (value = '') =>
  String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

function selectedNumbers(product) {
  const raw = product.final.selected_result_numbers || [];
  const actual = new Set(product.candidates.map((candidate) => candidate.number));
  if (raw.length && raw.every((number) => actual.has(number))) return new Set(raw);

  const mapped = raw
    .map((imageNumber) => product.candidates[imageNumber - 2]?.number)
    .filter(Boolean);
  return new Set(mapped);
}

function statusClass(status = '') {
  if (status.includes('точное')) return 'exact';
  if (status.includes('вероят')) return 'probable';
  return '';
}

function photoCard(item, selected) {
  return `
    <article class="photo-card ${selected ? 'selected' : ''}">
      <img src="${escapeHtml(item.file)}" alt="${escapeHtml(item.title)}" loading="lazy" />
      <div class="photo-meta">
        <span class="photo-label">${selected ? 'Выбрано AI' : `Результат ${item.number}`}</span>
        <p class="photo-title">${escapeHtml(item.title || 'Без названия')}</p>
        <div class="photo-source">
          <a href="${escapeHtml(item.page_url)}" target="_blank" rel="noreferrer">${escapeHtml(item.source || 'Открыть источник')}</a>
        </div>
      </div>
    </article>`;
}

function productCard(product, index) {
  const final = product.final;
  const selected = selectedNumbers(product);
  const facts = Object.entries(final.characteristics || {})
    .map(
      ([name, value]) => `
        <div class="fact">
          <dt>${escapeHtml(name.replaceAll('_', ' '))}</dt>
          <dd>${escapeHtml(value)}</dd>
        </div>`,
    )
    .join('');

  return `
    <section class="product">
      <div class="product-head">
        <div>
          <p class="product-number">Товар ${index + 1}</p>
          <h2>${escapeHtml(final.product_name_ru || product.caption)}</h2>
        </div>
        <span class="status ${statusClass(final.match_status_ru)}">
          ${escapeHtml(final.match_status_ru)} · ${escapeHtml(final.confidence_0_100)}%
        </span>
      </div>

      <div class="gallery">
        <article class="photo-card source">
          <img src="${escapeHtml(product.source_file)}" alt="Исходная фотография" />
          <div class="photo-meta">
            <span class="photo-label">Исходник</span>
            <p class="photo-title">${escapeHtml(product.caption)}</p>
            <div class="photo-source">Фото владельца</div>
          </div>
        </article>
        ${product.candidates.map((item) => photoCard(item, selected.has(item.number))).join('')}
      </div>

      <div class="details">
        <div class="info-block">
          <h3>Подпись исходника</h3>
          <p class="caption">${escapeHtml(product.caption)}</p>
          <h3>Что найдено</h3>
          <p><strong>${escapeHtml(final.brand_ru)}</strong></p>
          <p>${escapeHtml(final.description_ru)}</p>
          <dl class="facts">${facts}</dl>
        </div>
        <div class="info-block">
          <h3>Проверка совпадения</h3>
          <p class="comparison">${escapeHtml(final.comparison_ru)}</p>
          <p class="muted">${escapeHtml((final.uncertainties_ru || []).join(' · '))}</p>
        </div>
      </div>
    </section>`;
}

fetch('assets/serpapi-lab/review.json')
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then((products) => {
    root.innerHTML = products.map(productCard).join('');
  })
  .catch((error) => {
    root.innerHTML = `<p>Не удалось загрузить результаты: ${escapeHtml(error.message)}</p>`;
  });
