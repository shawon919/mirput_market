from django.db import models
from django.conf import settings
from django.utils import timezone
from cloudinary.models import CloudinaryField


CATEGORY_CHOICES = [
    ('veg', 'Vegetarian'),
    ('nonveg', 'Non-Vegetarian'),
    ('dessert', 'Dessert'),
    ('beverage', 'Beverage'),
]


class Product(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products"
    )

    cost_price = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0
)

    

    title = models.CharField(max_length=200)

    description = models.TextField()

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    stock = models.PositiveIntegerField(default=0)

    # Total quantity that has been sold through completed deliveries
    sold_quantity = models.PositiveIntegerField(default=0)

    image = CloudinaryField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.title

    @property
    def stock_status(self):
        if self.stock == 0:
            return "Out of Stock"

        return "In Stock"


class CartItem(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user} -> {self.product}"


class Order(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    address = models.TextField(
        default="Not provided"
    )

    payment_method = models.CharField(
        max_length=20,
        default="cod"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True
    )

    stock_deducted = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f"Order #{self.id}"

    @property
    def total_price(self):
        return self.product.price * self.quantity


class Sale(models.Model):
    """
    A Sale is created only when an order is successfully delivered.
    """

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="sale"
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales"
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchases"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sales"
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    sold_at = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):
        return f"Sale #{self.id} - {self.product.title}"


class ActivityLog(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_logs"
    )

    action = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.action}"
        

class Notification(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    message = models.CharField(
        max_length=255
    )

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):
        return self.message
    



class DeliveryConfirmation(models.Model):

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="delivery_confirmation"
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_confirmations"
    )

    seller_confirmed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    admin_confirmed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    admin_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_completed_deliveries"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return (
            f"Delivery Confirmation - "
            f"Order #{self.order.id}"
        )





class AppRevenue(models.Model):

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="app_revenue"
    )

    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE,
        related_name="app_revenue",
        null=True,
        blank=True
    )

    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    cost_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    profit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    revenue_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30
    )

    revenue_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):
        return f"App Revenue - Order #{self.order.id}"