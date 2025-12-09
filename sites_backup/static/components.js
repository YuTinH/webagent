/**
 * Enhanced UI Components Library
 *
 * Provides reusable interactive components:
 * - Modal dialogs
 * - Dropdown menus
 * - Shopping cart drawer
 * - Filter panels
 * - Toast notifications
 * - Tooltips
 */

// ============================================================================
// MODAL COMPONENT
// ============================================================================

class Modal {
  constructor(options = {}) {
    this.id = options.id || 'modal-' + Date.now();
    this.title = options.title || '';
    this.content = options.content || '';
    this.onConfirm = options.onConfirm || null;
    this.onCancel = options.onCancel || null;
    this.confirmText = options.confirmText || '确认';
    this.cancelText = options.cancelText || '取消';
    this.showCancel = options.showCancel !== false;

    this.element = null;
    this.isOpen = false;
  }

  create() {
    const modal = document.createElement('div');
    modal.id = this.id;
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal-container">
        <div class="modal-header">
          <h3 class="modal-title">${this.title}</h3>
          <button class="modal-close" aria-label="Close">×</button>
        </div>
        <div class="modal-body">
          ${this.content}
        </div>
        <div class="modal-footer">
          ${this.showCancel ? `<button class="btn modal-cancel">${this.cancelText}</button>` : ''}
          <button class="btn pri modal-confirm">${this.confirmText}</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    this.element = modal;

    // Event listeners
    modal.querySelector('.modal-close').addEventListener('click', () => this.close());
    modal.querySelector('.modal-confirm').addEventListener('click', () => this.confirm());
    if (this.showCancel) {
      modal.querySelector('.modal-cancel').addEventListener('click', () => this.cancel());
    }

    // Close on overlay click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) this.close();
    });

    // Close on ESC key
    this.escapeHandler = (e) => {
      if (e.key === 'Escape' && this.isOpen) this.close();
    };
    document.addEventListener('keydown', this.escapeHandler);

    return this;
  }

  open() {
    if (!this.element) this.create();
    this.element.classList.add('open');
    this.isOpen = true;
    document.body.style.overflow = 'hidden';
    return this;
  }

  close() {
    if (this.element) {
      this.element.classList.remove('open');
      this.isOpen = false;
      document.body.style.overflow = '';
      setTimeout(() => {
        if (this.element && this.element.parentNode) {
          this.element.parentNode.removeChild(this.element);
        }
        document.removeEventListener('keydown', this.escapeHandler);
      }, 300);
    }
    return this;
  }

  confirm() {
    if (this.onConfirm) {
      this.onConfirm();
    }
    this.close();
  }

  cancel() {
    if (this.onCancel) {
      this.onCancel();
    }
    this.close();
  }
}

// ============================================================================
// DROPDOWN COMPONENT
// ============================================================================

class Dropdown {
  constructor(triggerElement, options = {}) {
    this.trigger = triggerElement;
    this.items = options.items || [];
    this.onSelect = options.onSelect || null;
    this.align = options.align || 'left'; // left, right, center
    this.maxHeight = options.maxHeight || 300;

    this.dropdown = null;
    this.isOpen = false;

    this.init();
  }

  init() {
    this.trigger.style.position = 'relative';
    this.trigger.style.cursor = 'pointer';

    this.trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });

    // Close on outside click
    document.addEventListener('click', () => {
      if (this.isOpen) this.close();
    });
  }

  create() {
    const dropdown = document.createElement('div');
    dropdown.className = 'dropdown-menu';
    dropdown.style.maxHeight = this.maxHeight + 'px';

    if (this.align === 'right') {
      dropdown.style.right = '0';
    } else if (this.align === 'center') {
      dropdown.style.left = '50%';
      dropdown.style.transform = 'translateX(-50%)';
    }

    dropdown.innerHTML = this.items.map((item, index) => {
      if (item.divider) {
        return '<div class="dropdown-divider"></div>';
      }
      return `
        <div class="dropdown-item" data-index="${index}">
          ${item.icon ? `<span class="dropdown-icon">${item.icon}</span>` : ''}
          <span class="dropdown-label">${item.label}</span>
          ${item.badge ? `<span class="badge ${item.badge.type || ''}">${item.badge.text}</span>` : ''}
        </div>
      `;
    }).join('');

    this.trigger.appendChild(dropdown);
    this.dropdown = dropdown;

    // Add click handlers
    dropdown.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const index = parseInt(item.dataset.index);
        const selectedItem = this.items[index];
        if (this.onSelect && !selectedItem.divider) {
          this.onSelect(selectedItem, index);
        }
        this.close();
      });
    });
  }

  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  open() {
    if (!this.dropdown) this.create();
    this.dropdown.classList.add('open');
    this.isOpen = true;
  }

  close() {
    if (this.dropdown) {
      this.dropdown.classList.remove('open');
      this.isOpen = false;
    }
  }

  destroy() {
    if (this.dropdown && this.dropdown.parentNode) {
      this.dropdown.parentNode.removeChild(this.dropdown);
    }
  }
}

// ============================================================================
// CART DRAWER COMPONENT
// ============================================================================

class CartDrawer {
  constructor() {
    this.element = null;
    this.isOpen = false;
    this.cart = [];
  }

  create() {
    const drawer = document.createElement('div');
    drawer.id = 'cart-drawer';
    drawer.className = 'cart-drawer';
    drawer.innerHTML = `
      <div class="cart-drawer-overlay"></div>
      <div class="cart-drawer-content">
        <div class="cart-drawer-header">
          <h3>购物车</h3>
          <button class="cart-drawer-close" aria-label="Close">×</button>
        </div>
        <div class="cart-drawer-body">
          <div id="cart-items-list"></div>
        </div>
        <div class="cart-drawer-footer">
          <div class="cart-total">
            <span>总计:</span>
            <span id="cart-total-price" class="cart-total-price">¥0.00</span>
          </div>
            去结算
          </a>
        </div>
      </div>
    `;

    document.body.appendChild(drawer);
    this.element = drawer;

    // Event listeners
    drawer.querySelector('.cart-drawer-close').addEventListener('click', () => this.close());
    drawer.querySelector('.cart-drawer-overlay').addEventListener('click', () => this.close());

    return this;
  }

  open() {
    if (!this.element) this.create();
    this.loadCart();
    this.element.classList.add('open');
    this.isOpen = true;
    document.body.style.overflow = 'hidden';
    return this;
  }

  close() {
    if (this.element) {
      this.element.classList.remove('open');
      this.isOpen = false;
      document.body.style.overflow = '';
    }
    return this;
  }

  checkout() {
    const cartData = localStorage.getItem('cart') || '[]';
    localStorage.setItem('checkout-items', cartData);
    window.location.href = window.RelRoot + 'shop.local/checkout.html';
  }

  loadCart() {
    this.cart = JSON.parse(localStorage.getItem('cart') || '[]');
    this.render();
  }

  render() {
    const list = this.element.querySelector('#cart-items-list');

    if (this.cart.length === 0) {
      list.innerHTML = `
        <div class="cart-empty">
          <div style="font-size:48px; margin-bottom:16px; opacity:0.3">🛒</div>
          <div style="color:var(--muted)">购物车是空的</div>
        </div>
      `;
      this.element.querySelector('#cart-total-price').textContent = '¥0.00';
      return;
    }

    const total = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    list.innerHTML = this.cart.map((item, index) => `
      <div class="cart-item" data-index="${index}">
        <div class="cart-item-icon">${this.getCategoryIcon(item.category)}</div>
        <div class="cart-item-info">
          <div class="cart-item-name">${this.escapeHtml(item.name)}</div>
          <div class="cart-item-price">¥${item.price.toFixed(2)} × ${item.quantity}</div>
        </div>
        <button class="cart-item-remove" onclick="cartDrawer.removeItem(${index})" aria-label="Remove">×</button>
      </div>
    `).join('');

    this.element.querySelector('#cart-total-price').textContent = `¥${total.toFixed(2)}`;
  }

  removeItem(index) {
    this.cart.splice(index, 1);
    localStorage.setItem('cart', JSON.stringify(this.cart));
    this.render();

    // Update cart badge if exists
    if (typeof updateCartCount === 'function') {
      updateCartCount();
    }
  }

  getCategoryIcon(category) {
    const icons = {
      'electronics': '🖱️',
      'home': '🏠',
      'books': '📚',
      'sports': '⚽',
      'fashion': '👕',
      'toys': '🧸',
      'food': '🍜'
    };
    return icons[category] || '📦';
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Global cart drawer instance
window.cartDrawer = null;

function openCartDrawer() {
  if (!window.cartDrawer) {
    window.cartDrawer = new CartDrawer();
  }
  window.cartDrawer.open();
}

// ============================================================================
// FILTER PANEL COMPONENT
// ============================================================================

class FilterPanel {
  constructor(options = {}) {
    this.filters = options.filters || [];
    this.onApply = options.onApply || null;
    this.onReset = options.onReset || null;
    this.activeFilters = {};
  }

  render(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
      <div class="filter-panel">
        <div class="filter-header">
          <h3>筛选</h3>
          <button class="filter-reset" onclick="filterPanel.reset()">重置</button>
        </div>
        <div class="filter-body">
          ${this.filters.map((filter, index) => this.renderFilter(filter, index)).join('')}
        </div>
        <div class="filter-footer">
          <button class="btn pri" onclick="filterPanel.apply()">应用筛选</button>
        </div>
      </div>
    `;
  }

  renderFilter(filter, index) {
    switch (filter.type) {
      case 'checkbox':
        return `
          <div class="filter-group">
            <div class="filter-group-title">${filter.label}</div>
            ${filter.options.map(option => `
              <label class="filter-checkbox">
                <input type="checkbox" name="${filter.key}" value="${option.value}" onchange="filterPanel.updateFilter('${filter.key}', '${option.value}', this.checked)">
                <span>${option.label}</span>
                ${option.count ? `<span class="filter-count">(${option.count})</span>` : ''}
              </label>
            `).join('')}
          </div>
        `;

      case 'range':
        return `
          <div class="filter-group">
            <div class="filter-group-title">${filter.label}</div>
            <div class="filter-range">
              <input type="number" placeholder="最小" id="filter-${filter.key}-min" onchange="filterPanel.updateRangeFilter('${filter.key}', 'min', this.value)">
              <span>-</span>
              <input type="number" placeholder="最大" id="filter-${filter.key}-max" onchange="filterPanel.updateRangeFilter('${filter.key}', 'max', this.value)">
            </div>
          </div>
        `;

      case 'rating':
        return `
          <div class="filter-group">
            <div class="filter-group-title">${filter.label}</div>
            ${[5,4,3,2,1].map(rating => `
              <label class="filter-checkbox">
                <input type="radio" name="${filter.key}" value="${rating}" onchange="filterPanel.updateFilter('${filter.key}', ${rating}, true)">
                <span>${'★'.repeat(rating)}${'☆'.repeat(5-rating)} 及以上</span>
              </label>
            `).join('')}
          </div>
        `;

      default:
        return '';
    }
  }

  updateFilter(key, value, checked) {
    if (!this.activeFilters[key]) {
      this.activeFilters[key] = [];
    }

    if (checked) {
      if (!this.activeFilters[key].includes(value)) {
        this.activeFilters[key].push(value);
      }
    } else {
      this.activeFilters[key] = this.activeFilters[key].filter(v => v !== value);
    }
  }

  updateRangeFilter(key, type, value) {
    if (!this.activeFilters[key]) {
      this.activeFilters[key] = {};
    }
    this.activeFilters[key][type] = value;
  }

  apply() {
    if (this.onApply) {
      this.onApply(this.activeFilters);
    }
  }

  reset() {
    this.activeFilters = {};
    document.querySelectorAll('.filter-panel input[type="checkbox"], .filter-panel input[type="radio"]').forEach(input => {
      input.checked = false;
    });
    document.querySelectorAll('.filter-panel input[type="number"]').forEach(input => {
      input.value = '';
    });

    if (this.onReset) {
      this.onReset();
    }
  }
}

// Global filter panel instance
let filterPanel = null;

// ============================================================================
// TOAST NOTIFICATION
// ============================================================================

class Toast {
  static show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
      <div class="toast-content">
        ${this.getIcon(type)}
        <span>${message}</span>
      </div>
    `;

    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after duration
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, duration);
  }

  static getIcon(type) {
    const icons = {
      'success': '✓',
      'error': '✕',
      'warning': '⚠',
      'info': 'ℹ'
    };
    return `<span class="toast-icon">${icons[type] || icons.info}</span>`;
  }

  static success(message, duration) {
    this.show(message, 'success', duration);
  }

  static error(message, duration) {
    this.show(message, 'error', duration);
  }

  static warning(message, duration) {
    this.show(message, 'warning', duration);
  }

  static info(message, duration) {
    this.show(message, 'info', duration);
  }
}

// ============================================================================
// RATING COMPONENT
// ============================================================================

class Rating {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.value = options.value || 0;
    this.readonly = options.readonly || false;
    this.onChange = options.onChange || null;

    if (this.container) {
      this.render();
    }
  }

  render() {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      const filled = i <= this.value;
      stars.push(`
        <span class="rating-star ${filled ? 'filled' : ''}" data-value="${i}" ${!this.readonly ? 'onclick="this.closest(\'.rating-component\').ratingInstance.setValue(' + i + ')"' : ''}>
          ${filled ? '★' : '☆'}
        </span>
      `);
    }

    this.container.innerHTML = `
      <div class="rating-component ${this.readonly ? 'readonly' : ''}">
        ${stars.join('')}
      </div>
    `;

    // Store instance on element for access in onclick
    this.container.querySelector('.rating-component').ratingInstance = this;
  }

  setValue(value) {
    if (this.readonly) return;
    this.value = value;
    this.render();
    if (this.onChange) {
      this.onChange(value);
    }
  }

  getValue() {
    return this.value;
  }
}

// ============================================================================
// TABS COMPONENT
// ============================================================================

class Tabs {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.tabs = options.tabs || [];
    this.activeIndex = options.activeIndex || 0;
    this.onChange = options.onChange || null;

    if (this.container) {
      this.render();
    }
  }

  render() {
    const tabButtons = this.tabs.map((tab, index) => `
      <button class="tab-button ${index === this.activeIndex ? 'active' : ''}" onclick="this.closest('.tabs-component').tabsInstance.setActive(${index})">
        ${tab.icon ? `<span class="tab-icon">${tab.icon}</span>` : ''}
        ${tab.label}
        ${tab.badge ? `<span class="badge ${tab.badge.type || ''}">${tab.badge.text}</span>` : ''}
      </button>
    `).join('');

    const tabContents = this.tabs.map((tab, index) => `
      <div class="tab-panel ${index === this.activeIndex ? 'active' : ''}" data-index="${index}">
        ${tab.content || ''}
      </div>
    `).join('');

    this.container.innerHTML = `
      <div class="tabs-component">
        <div class="tabs-header">
          ${tabButtons}
        </div>
        <div class="tabs-body">
          ${tabContents}
        </div>
      </div>
    `;

    // Store instance
    this.container.querySelector('.tabs-component').tabsInstance = this;
  }

  setActive(index) {
    if (index < 0 || index >= this.tabs.length) return;

    this.activeIndex = index;

    // Update buttons
    this.container.querySelectorAll('.tab-button').forEach((btn, i) => {
      btn.classList.toggle('active', i === index);
    });

    // Update panels
    this.container.querySelectorAll('.tab-panel').forEach((panel, i) => {
      panel.classList.toggle('active', i === index);
    });

    if (this.onChange) {
      this.onChange(index, this.tabs[index]);
    }
  }
}

// ============================================================================
// EXPORT (if using modules)
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    Modal,
    Dropdown,
    CartDrawer,
    FilterPanel,
    Toast,
    Rating,
    Tabs
  };
}
