"""
Dynamic Perturbation Engine

This module handles:
1. DOM shuffling and element randomization
2. Dynamic pricing and inventory
3. CSS class randomization
4. Form validation errors
5. Session management
6. Error injection

All perturbations are deterministic based on seed for reproducibility.
"""

import random
import re
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class PerturbationLevel:
    """Difficulty levels"""
    BASELINE = 1      # No perturbations
    LIGHT = 2         # CSS/order shuffling
    MEDIUM = 3        # Dynamic content, resource constraints
    ADVANCED = 4      # Error scenarios, session management
    EXPERT = 5        # Full DOM shuffle, semantic equivalents


class DOMShuffler:
    """Shuffles DOM elements based on seed"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def shuffle_navigation(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Shuffle navigation menu items"""
        nav = soup.find('nav')
        if nav:
            items = nav.find_all('li', recursive=False)
            if items:
                items_list = list(items)
                self.rng.shuffle(items_list)

                # Clear and re-add in shuffled order
                for item in items:
                    item.extract()
                for item in items_list:
                    nav.append(item)

        return soup

    def shuffle_product_grid(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Shuffle product cards in grid"""
        grid = soup.find(class_=re.compile(r'product-grid|products-container'))
        if grid:
            cards = grid.find_all(class_=re.compile(r'product-card|product-item'))
            if cards:
                cards_list = list(cards)
                self.rng.shuffle(cards_list)

                # Clear and re-add
                for card in cards:
                    card.extract()
                for card in cards_list:
                    grid.append(card)

        return soup

    def shuffle_form_fields(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Shuffle form field order"""
        forms = soup.find_all('form')
        for form in forms:
            # Find all direct children that are form groups/fields
            fields = form.find_all(class_=re.compile(r'form-group|field|input-group'), recursive=False)
            if fields and len(fields) > 1:
                # Don't shuffle submit button
                submit_btn = form.find('button', type='submit')
                if submit_btn:
                    submit_btn.extract()

                fields_list = list(fields)
                self.rng.shuffle(fields_list)

                for field in fields:
                    field.extract()
                for field in fields_list:
                    form.append(field)

                if submit_btn:
                    form.append(submit_btn)

        return soup

    def randomize_css_classes(self, soup: BeautifulSoup, level: int = 2) -> BeautifulSoup:
        """
        Randomize CSS class names to semantic equivalents

        Level 2: Simple renaming (btn → button)
        Level 5: Complete semantic changes (button → div[onclick])
        """
        if level < 2:
            return soup

        # CSS class equivalents
        equivalents = {
            'btn': ['button', 'action-btn', 'clickable', 'btn-action'],
            'card': ['item', 'box', 'container', 'panel'],
            'input': ['field', 'textbox', 'form-control', 'input-field'],
            'product-card': ['product-item', 'item-card', 'product-box'],
            'container': ['wrapper', 'content-wrap', 'main-container'],
        }

        for elem in soup.find_all(class_=True):
            new_classes = []
            for cls in elem.get('class', []):
                if cls in equivalents:
                    new_classes.append(self.rng.choice(equivalents[cls]))
                else:
                    new_classes.append(cls)
            elem['class'] = new_classes

        return soup

    def apply_full_shuffle(self, html: str, level: int = 5) -> str:
        """Apply all DOM shuffling transformations"""
        soup = BeautifulSoup(html, 'html.parser')

        if level >= 2:
            soup = self.shuffle_navigation(soup)
            soup = self.randomize_css_classes(soup, level)

        if level >= 3:
            soup = self.shuffle_product_grid(soup)

        if level >= 4:
            soup = self.shuffle_form_fields(soup)

        if level >= 5:
            soup = self.apply_semantic_equivalents(soup)

        return str(soup)

    def apply_semantic_equivalents(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Replace elements with semantic equivalents

        Example: <button> → <div onclick="...">
        """
        # Replace some buttons with divs
        buttons = soup.find_all('button', class_='btn')
        for i, btn in enumerate(buttons):
            if self.rng.random() < 0.3:  # 30% chance
                div = soup.new_tag('div')
                div['class'] = btn.get('class', [])
                div['onclick'] = f"handleClick('{btn.get('id', f'btn-{i}')}')"
                div.string = btn.get_text()
                btn.replace_with(div)

        return soup


class DynamicContentManager:
    """Manages dynamic content (prices, inventory, etc.)"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.price_multipliers = {}
        self.stock_levels = {}

    def get_dynamic_price(self, sku: str, base_price: float, variance: float = 0.2) -> float:
        """
        Get price with variance based on seed

        variance=0.2 means ±20% variation
        """
        if sku not in self.price_multipliers:
            self.price_multipliers[sku] = self.rng.uniform(1 - variance, 1 + variance)

        return round(base_price * self.price_multipliers[sku], 2)

    def get_dynamic_stock(self, sku: str, base_stock: int = 10, variance: int = 5) -> int:
        """
        Get stock level with variance

        variance=5 means ±5 units
        """
        if sku not in self.stock_levels:
            variation = self.rng.randint(-variance, variance)
            self.stock_levels[sku] = max(0, base_stock + variation)

        return self.stock_levels[sku]

    def is_out_of_stock(self, sku: str, probability: float = 0.1) -> bool:
        """Random chance of being out of stock"""
        return self.rng.random() < probability

    def apply_to_product_page(self, html: str) -> str:
        """Apply dynamic pricing and stock to HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all product cards
        products = soup.find_all(class_=re.compile(r'product-card|product-item'))

        for product in products:
            # Get SKU
            sku = product.get('data-sku', '')
            if not sku:
                continue

            # Update price
            price_elem = product.find(class_=re.compile(r'price|product-price'))
            if price_elem:
                try:
                    current_price = float(price_elem.get_text().replace('$', '').strip())
                    new_price = self.get_dynamic_price(sku, current_price)
                    price_elem.string = f"${new_price:.2f}"
                except ValueError:
                    pass

            # Update stock
            stock = self.get_dynamic_stock(sku)
            if stock == 0 or self.is_out_of_stock(sku):
                # Add out of stock indicator
                product['class'] = product.get('class', []) + ['out-of-stock']
                buy_btn = product.find('button', class_=re.compile(r'add-to-cart|buy'))
                if buy_btn:
                    buy_btn['disabled'] = 'disabled'
                    buy_btn.string = 'Out of Stock'

        return str(soup)


class ErrorInjector:
    """Injects realistic errors and failures"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def should_inject_error(self, error_type: str, base_probability: float = 0.1) -> bool:
        """Determine if an error should be injected"""
        return self.rng.random() < base_probability

    def get_payment_error(self) -> Optional[Dict[str, str]]:
        """Simulate payment processing errors"""
        if self.should_inject_error('payment', 0.15):
            errors = [
                {
                    'type': 'timeout',
                    'message': 'Payment gateway timeout. Please try again.',
                    'recoverable': True
                },
                {
                    'type': 'insufficient_funds',
                    'message': 'Payment declined: Insufficient funds',
                    'recoverable': False
                },
                {
                    'type': 'card_declined',
                    'message': 'Card declined by issuer',
                    'recoverable': True
                },
                {
                    'type': 'network_error',
                    'message': 'Network error during payment processing',
                    'recoverable': True
                }
            ]
            return self.rng.choice(errors)
        return None

    def get_form_validation_error(self, field: str) -> Optional[str]:
        """Simulate form validation errors"""
        if self.should_inject_error('validation', 0.2):
            errors = {
                'address': 'Address not in service area',
                'zipcode': 'Invalid ZIP code format',
                'phone': 'Phone number must be 10 digits',
                'email': 'Email address is already registered',
                'vehicle_year': 'Vehicle must be 2010 or newer'
            }
            return errors.get(field)
        return None

    def get_session_error(self, session_age_seconds: int) -> Optional[Dict[str, str]]:
        """Check for session timeout or conflicts"""
        if session_age_seconds > 300:  # 5 minutes
            return {
                'type': 'session_expired',
                'message': 'Your session has expired. Please login again.',
                'recoverable': True
            }

        if self.should_inject_error('session_conflict', 0.05):
            return {
                'type': 'concurrent_session',
                'message': 'You have been logged out due to login from another device.',
                'recoverable': True
            }

        return None


class SessionManager:
    """Manages session state and timeouts"""

    def __init__(self):
        self.sessions = {}
        self.session_timeout = 300  # 5 minutes

    def create_session(self, user_id: str) -> str:
        """Create a new session"""
        session_id = f"sess_{user_id}_{int(datetime.now().timestamp())}"
        self.sessions[session_id] = {
            'user_id': user_id,
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
        return session_id

    def is_valid(self, session_id: str) -> bool:
        """Check if session is still valid"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        age = (datetime.now() - session['last_activity']).total_seconds()

        return age < self.session_timeout

    def touch(self, session_id: str):
        """Update last activity time"""
        if session_id in self.sessions:
            self.sessions[session_id]['last_activity'] = datetime.now()


class PerturbationEngine:
    """
    Main engine that applies all perturbations based on difficulty level
    """

    def __init__(self, seed: int = 42, level: int = PerturbationLevel.BASELINE):
        self.seed = seed
        self.level = level
        self.dom_shuffler = DOMShuffler(seed)
        self.content_manager = DynamicContentManager(seed)
        self.error_injector = ErrorInjector(seed)
        self.session_manager = SessionManager()

    def perturb_page(self, html: str, page_type: str = 'product') -> str:
        """
        Apply perturbations to a page based on difficulty level

        page_type: 'product', 'checkout', 'account', etc.
        """
        if self.level == PerturbationLevel.BASELINE:
            return html

        # Level 2+: DOM shuffling and CSS randomization
        if self.level >= PerturbationLevel.LIGHT:
            html = self.dom_shuffler.apply_full_shuffle(html, level=self.level)

        # Level 3+: Dynamic content
        if self.level >= PerturbationLevel.MEDIUM:
            if page_type == 'product':
                html = self.content_manager.apply_to_product_page(html)

        # Level 4+: Error injection (handled during task execution)
        # Level 5: Full semantic equivalents (already in DOM shuffler)

        return html

    def should_inject_payment_error(self) -> Optional[Dict[str, str]]:
        """Check if payment error should be injected"""
        if self.level >= PerturbationLevel.ADVANCED:
            return self.error_injector.get_payment_error()
        return None

    def should_inject_form_error(self, field: str) -> Optional[str]:
        """Check if form validation error should be injected"""
        if self.level >= PerturbationLevel.MEDIUM:
            return self.error_injector.get_form_validation_error(field)
        return None

    def check_session_valid(self, session_id: str, session_age: int) -> Tuple[bool, Optional[str]]:
        """Check if session is valid"""
        if self.level >= PerturbationLevel.ADVANCED:
            error = self.error_injector.get_session_error(session_age)
            if error:
                return False, error['message']

            if not self.session_manager.is_valid(session_id):
                return False, "Session expired"

        return True, None

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of current perturbation configuration"""
        return {
            'seed': self.seed,
            'level': self.level,
            'level_name': self.get_level_name(self.level),
            'features': self.get_enabled_features(),
            'expected_success_rate': self.get_expected_success_rate()
        }

    def get_level_name(self, level: int) -> str:
        """Get human-readable level name"""
        names = {
            1: 'Baseline (No Perturbations)',
            2: 'Light (CSS/DOM Shuffling)',
            3: 'Medium (Dynamic Content)',
            4: 'Advanced (Error Injection)',
            5: 'Expert (Full Semantic Equivalents)'
        }
        return names.get(level, 'Unknown')

    def get_enabled_features(self) -> List[str]:
        """Get list of enabled perturbation features"""
        features = []

        if self.level >= 2:
            features.extend(['DOM Shuffling', 'CSS Randomization'])

        if self.level >= 3:
            features.extend(['Dynamic Pricing', 'Dynamic Inventory', 'Out of Stock'])

        if self.level >= 4:
            features.extend(['Payment Errors', 'Form Validation', 'Session Timeout'])

        if self.level >= 5:
            features.extend(['Semantic Equivalents', 'Full DOM Shuffle'])

        return features

    def get_expected_success_rate(self) -> str:
        """Get expected agent success rate for this level"""
        rates = {
            1: '90-100%',
            2: '70-90%',
            3: '50-70%',
            4: '30-50%',
            5: '10-30%'
        }
        return rates.get(self.level, 'Unknown')


# Example usage
if __name__ == "__main__":
    # Test Level 3 (Medium)
    engine = PerturbationEngine(seed=42, level=PerturbationLevel.MEDIUM)

    print("=== Perturbation Engine Configuration ===")
    config = engine.get_configuration_summary()
    for key, value in config.items():
        print(f"{key}: {value}")

    # Test DOM shuffling
    sample_html = """
    <html>
    <body>
        <nav>
            <ul>
                <li><a href="/home">Home</a></li>
                <li><a href="/products">Products</a></li>
                <li><a href="/cart">Cart</a></li>
            </ul>
        </nav>
        <div class="product-grid">
            <div class="product-card" data-sku="WM-5521">
                <h3>Wireless Mouse</h3>
                <p class="price">$29.99</p>
                <button class="btn add-to-cart">Add to Cart</button>
            </div>
            <div class="product-card" data-sku="KB-8801">
                <h3>Mechanical Keyboard</h3>
                <p class="price">$89.99</p>
                <button class="btn add-to-cart">Add to Cart</button>
            </div>
        </div>
    </body>
    </html>
    """

    perturbed = engine.perturb_page(sample_html, 'product')
    print("\n=== Perturbed HTML (snippet) ===")
    print(perturbed[:500])

    # Test error injection
    print("\n=== Testing Error Injection ===")
    for i in range(5):
        payment_error = engine.should_inject_payment_error()
        if payment_error:
            print(f"Payment Error: {payment_error['message']}")

    # Test dynamic pricing
    print("\n=== Testing Dynamic Pricing ===")
    for sku in ["WM-5521", "KB-8801", "HD-9901"]:
        price = engine.content_manager.get_dynamic_price(sku, 29.99)
        stock = engine.content_manager.get_dynamic_stock(sku)
        print(f"{sku}: ${price:.2f}, Stock: {stock}")
