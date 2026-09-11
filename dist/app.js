const products = [
  { id:'lamp', name:'Trail Lantern', price:28, icon:'◉', description:'Warm, rechargeable light for camp and patio.' },
  { id:'bottle', name:'Steel Bottle', price:22, icon:'◐', description:'Insulated 24-ounce bottle with a secure lid.' },
  { id:'tote', name:'Utility Tote', price:34, icon:'▰', description:'A sturdy canvas carryall with six pockets.' }
];

let cart = JSON.parse(localStorage.getItem('northstar-cart') || '[]');
let discount = null;
let shipping = 'standard';
let removedItem = null;
let staleSubtotal = null;

const money = value => `$${value.toFixed(2)}`;
const saveCart = () => localStorage.setItem('northstar-cart', JSON.stringify(cart));
const actualSubtotal = () => cart.reduce((sum,item) => sum + item.price * item.quantity, 0);

function showView(name) {
  document.querySelectorAll('.view').forEach(view => view.hidden = true);
  document.getElementById(`${name}-view`).hidden = false;
  document.querySelectorAll('.nav-button').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  location.hash = name;
  render();
}

function renderProducts() {
  document.getElementById('product-grid').innerHTML = products.map(product => `
    <article class="product-card">
      <div class="product-icon" aria-hidden="true">${product.icon}</div>
      <h2>${product.name}</h2><p>${product.description}</p>
      <div class="product-footer"><strong>${money(product.price)}</strong><button data-add="${product.id}">Add to cart</button></div>
    </article>`).join('');
}

function renderCart() {
  const region = document.getElementById('cart-items');
  region.innerHTML = cart.length ? cart.map(item => `
    <article class="cart-item" data-product="${item.id}">
      <div><h2>${item.name}</h2><p>${money(item.price)} each</p></div>
      <div class="quantity" aria-label="Quantity for ${item.name}">
        <button aria-label="Decrease ${item.name} quantity" data-decrease="${item.id}">−</button>
        <strong aria-label="Current quantity">${item.quantity}</strong>
        <button aria-label="Increase ${item.name} quantity" data-increase="${item.id}">+</button>
      </div>
      <button class="remove" data-remove="${item.id}">Remove</button>
    </article>`).join('') : '<p class="empty">Your cart is empty.</p>';

  const subtotal = staleSubtotal ?? actualSubtotal();
  const discountAmount = discount === 'SAVE10' ? actualSubtotal() * .1 : 0;
  const shippingAmount = shipping === 'express' ? 12 : 0;
  const total = actualSubtotal() - discountAmount + shippingAmount + (shipping === 'express' ? 12 : 0);
  document.getElementById('subtotal').textContent = money(subtotal);
  document.getElementById('discount-line').hidden = !discountAmount;
  document.getElementById('discount-amount').textContent = `-${money(discountAmount)}`;
  document.getElementById('total').textContent = money(total);
  document.getElementById('cart-count').textContent = cart.reduce((sum,item) => sum + item.quantity, 0);
}

function render() { renderProducts(); renderCart(); }

document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.view) return showView(button.dataset.view);
  if (button.dataset.add) {
    staleSubtotal = null;
    const product = products.find(p => p.id === button.dataset.add);
    const existing = cart.find(item => item.id === product.id);
    existing ? existing.quantity++ : cart.push({...product, quantity:1});
    saveCart(); render();
  }
  if (button.dataset.increase) {
    staleSubtotal = actualSubtotal();
    cart.find(item => item.id === button.dataset.increase).quantity++;
    saveCart(); render();
  }
  if (button.dataset.decrease) {
    staleSubtotal = null;
    const item = cart.find(item => item.id === button.dataset.decrease);
    item.quantity = Math.max(1, item.quantity - 1);
    saveCart(); render();
  }
  if (button.dataset.remove) {
    staleSubtotal = null;
    const index = cart.findIndex(item => item.id === button.dataset.remove);
    removedItem = cart.splice(index,1)[0];
    saveCart();
    document.getElementById('undo-message').textContent = `${removedItem.name} removed.`;
    document.getElementById('undo-region').hidden = false;
    render();
  }
});

document.getElementById('undo-button').addEventListener('click', () => {
  if (!removedItem) return;
  cart.push({...removedItem}); cart.push({...removedItem});
  removedItem = null; saveCart();
  document.getElementById('undo-region').hidden = true; render();
});

document.getElementById('apply-discount').addEventListener('click', () => {
  const code = document.getElementById('discount-code').value.trim().toUpperCase();
  if (code === 'SAVE10') { discount = code; document.getElementById('discount-message').textContent = '10% discount applied.'; }
  else { discount = null; document.getElementById('discount-message').textContent = 'Code not recognized.'; }
  render();
});

document.querySelectorAll('input[name="shipping"]').forEach(input => input.addEventListener('change', event => { shipping = event.target.value; render(); }));
document.getElementById('checkout-form').addEventListener('submit', event => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  document.getElementById('form-error').textContent = [...data.values()].some(value => !String(value).trim()) ? 'Some information is missing. Please check the form.' : 'Order submission is disabled in this demonstration.';
});

window.addEventListener('hashchange', () => showView(location.hash.slice(1) || 'products'));
showView(['products','cart','checkout'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'products');

