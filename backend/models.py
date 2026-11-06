"""Global discovery schema. Money is stored in integer minor units with a currency."""
from datetime import date, datetime, timezone
from sqlalchemy import String, Date, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str]
    persona: Mapped[str]
    home_currency: Mapped[str] = mapped_column(default='USD')


class Currency(Base):
    __tablename__ = 'currencies'
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str]
    exponent: Mapped[int]


class Country(Base):
    __tablename__ = 'countries'
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str]
    map_id: Mapped[str] = mapped_column(unique=True)
    currency: Mapped[str] = mapped_column(ForeignKey('currencies.code'))
    longitude: Mapped[float]
    latitude: Mapped[float]


class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]
    category: Mapped[str] = mapped_column(index=True)
    kind: Mapped[str]
    image_url: Mapped[str]
    equivalence_group: Mapped[str | None]


class Offer(Base):
    __tablename__ = 'product_offers'
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    country_code: Mapped[str] = mapped_column(ForeignKey('countries.code'), index=True)
    merchant_name: Mapped[str] = mapped_column(default='Commerce Radar Demo Merchant')
    currency: Mapped[str] = mapped_column(ForeignKey('currencies.code'))
    local_price: Mapped[int]
    shipping: Mapped[int | None]
    taxes: Mapped[int | None]
    other_fees: Mapped[int | None]
    available_in_japan: Mapped[bool | None]
    stock: Mapped[int]
    paypal_eligible: Mapped[bool]
    checkout_jpy: Mapped[int | None]
    checkout_usd: Mapped[int | None]
    available_in_us: Mapped[bool | None]
    comparison_reference_jpy: Mapped[int | None]
    product_url: Mapped[str | None]
    refund_terms: Mapped[str]
    source: Mapped[str] = mapped_column(default='Synthetic Demo Catalog')
    verified_at: Mapped[datetime] = mapped_column(default=now)
    __table_args__ = (CheckConstraint('local_price > 0'), CheckConstraint('stock >= 0'))


class Purchase(Base):
    __tablename__ = 'purchase_transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey('product_offers.id'))
    product_name: Mapped[str]
    category: Mapped[str] = mapped_column(index=True)
    merchant_name: Mapped[str]
    country_code: Mapped[str]
    quantity: Mapped[int] = mapped_column(default=1)
    amount: Mapped[int]
    currency: Mapped[str]
    purchased_at: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str]
    notes: Mapped[str] = mapped_column(Text, default='')
    deleted: Mapped[bool] = mapped_column(default=False)
    paypal_order_id: Mapped[str | None] = mapped_column(unique=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(unique=True)
    legacy_id: Mapped[str | None] = mapped_column(unique=True)
    __table_args__ = (CheckConstraint('amount > 0'),)


class InterestProfile(Base):
    __tablename__ = 'interest_profiles'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    overrides_json: Mapped[str | None] = mapped_column(Text)
    budget_jpy: Mapped[int] = mapped_column(default=15000)
    budget_usd: Mapped[int] = mapped_column(default=15000)
    updated_at: Mapped[datetime] = mapped_column(default=now)


class ExchangeRate(Base):
    __tablename__ = 'exchange_rates'
    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(ForeignKey('currencies.code'))
    quote: Mapped[str] = mapped_column(default='JPY')
    rate: Mapped[str]  # Decimal string: JPY per 1 foreign currency unit
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(index=True)
    fetched_at: Mapped[datetime] = mapped_column(default=now)
    __table_args__ = (UniqueConstraint('base', 'quote', 'rate_date', 'source'),)


class DemoScenario(Base):
    __tablename__ = 'demo_scenarios'
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    description: Mapped[str]
    current_multiplier: Mapped[str]


class SavedOpportunity(Base):
    __tablename__ = 'saved_opportunities'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey('product_offers.id'))
    created_at: Mapped[datetime] = mapped_column(default=now)
    __table_args__ = (UniqueConstraint('user_id', 'offer_id'),)


class PaymentOrder(Base):
    __tablename__ = 'checkout_orders'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    consumer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey('product_offers.id'))
    product_name: Mapped[str]
    category: Mapped[str]
    country_code: Mapped[str]
    quantity: Mapped[int]
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(default='JPY')
    mode: Mapped[str]
    status: Mapped[str] = mapped_column(default='CREATING')
    paypal_order_id: Mapped[str | None] = mapped_column(unique=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(unique=True)
    approval_url: Mapped[str | None]
    request_key: Mapped[str] = mapped_column(unique=True)
    capture_key: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(default=now)
    __table_args__ = (CheckConstraint('quantity > 0'), CheckConstraint('amount > 0'))


class PaymentEvent(Base):
    __tablename__ = 'payment_transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('checkout_orders.id'), index=True)
    event_type: Mapped[str]
    event_status: Mapped[str]
    external_event_id: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(default=now)


class AICache(Base):
    __tablename__ = 'ai_cache'
    key: Mapped[str] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)


class MigrationState(Base):
    __tablename__ = 'migration_state'
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class AnalysisState(Base):
    __tablename__ = 'analysis_states'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    version: Mapped[int] = mapped_column(default=1)
    applied_version: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default='pending')
    result_json: Mapped[str | None] = mapped_column(Text)
    previous_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None]
    feedback: Mapped[str] = mapped_column(Text, default='')
    calls: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)


class ChatState(Base):
    __tablename__ = 'chat_states'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    conditions_json: Mapped[str] = mapped_column(Text, default='{}')
    messages_json: Mapped[str] = mapped_column(Text, default='[]')


class APIUsage(Base):
    __tablename__ = 'api_usage'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    feature: Mapped[str]
    model: Mapped[str]
    status: Mapped[str]
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)
