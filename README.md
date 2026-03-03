# Viatges Carcaixent - Flight & Tours Booking System

A full-stack Flask-based travel booking platform integrating Duffel Flights API, Amadeus, and Stripe for flight and tour reservations.

## Features

- **Flight Search & Booking**: Real-time search via Duffel API and Amadeus
- **Payment Processing**: Stripe checkout + emisión de reservas con Duffel Balance
- **Tour Management**: Dynamic tour packages with customizable itineraries
- **Admin Panel**: Comprehensive dashboard for bookings, reservations, and analytics
- **User Authentication**: Secure login and session management
- **Email Notifications**: Automated confirmation and status updates
- **Monitoring**: Prometheus metrics and rotating logs
- **Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations

## Tech Stack

- **Backend**: Flask 2.x, SQLAlchemy, PostgreSQL
- **Frontend**: HTML5, CSS3, Vanilla JavaScript, Flatpickr
- **Payment**: Stripe, Duffel Balance
- **APIs**: Duffel Flights, Amadeus, EmailManager
- **Deployment**: Docker Compose, Gunicorn, Nginx
- **Monitoring**: Prometheus, Rotating File Logs

## Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Redis (optional, for caching)
- Docker & Docker Compose plugin (for containerized deployment)

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd agencia
```

### 2. Set Up Environment Variables
```bash
cp .env.example .env
# Edit .env with your actual credentials:
# - Database settings
# - API keys (Duffel, Amadeus, Stripe)
# - Email configuration
# - Secret keys
```

### 3. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Initialize Database
```bash
export FLASK_APP=app.py
flask db upgrade
```

### 5. Run Development Server
```bash
python app.py
# Or with gunicorn: gunicorn -c gunicorn_config.py app:app
```

Visit `http://localhost:8000` in your browser.

## Docker Deployment

```bash
docker compose up -d
```

This starts:
- PostgreSQL database on port 5433
- Redis cache (optional)
- Prometheus on port 9090
- Grafana on port 3000
- PgAdmin on port 5050

## Project Structure

```
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Container orchestration
├── gunicorn_config.py     # Gunicorn server configuration
│
├── api/                   # API modules
│   ├── schemas.py         # Request validation
│   └── decorators.py      # Authentication decorators
│
├── blueprints/            # Flask blueprints auxiliares
│   └── tours.py
│
├── core/                  # Business logic & utilities
│   ├── scraper_motor.py   # Duffel API integration
│   ├── email_service.py   # Email notifications
│   ├── security.py        # Authentication & encryption
│   └── tasks.py           # Scheduled background tasks
│
├── database/              # Database layer
│   ├── models.py          # SQLAlchemy models
│   └── connection.py      # DB session management
│
├── templates/             # Jinja2 HTML templates
│   ├── index.html         # Flight search form
│   ├── checkout.html      # Payment page
│   └── admin/             # Admin dashboard
│
├── static/                # Frontend assets
│   ├── js/
│   ├── css/
│   └── images/
│
├── migrations/            # Database migration scripts
│
├── alembic/               # DB version control with Alembic
│
└── monitoring/            # Prometheus metrics & configs
```

## API Endpoints

### Flights
- `GET /api/vuelos/search` - Search flights
- `POST /api/vuelos/crear-reserva` - Create reservation
- `GET /api/vuelos/<id>` - Get flight details

### Payments
- `POST /api/vuelos/create-checkout-session` - Crear sesión Stripe Checkout
- `POST /webhook/stripe` - Confirmación de pago Stripe y emisión Duffel balance

### Orders
- `GET /api/orders` - List user orders
- `POST /api/orders/<id>/cancel` - Cancel order

### Admin
- `GET /admin/dashboard` - Admin overview
- `GET /admin/reservas` - All reservations
- `POST /admin/reservas/<id>/update` - Update reservation

### Webhooks
- `POST /webhook/stripe` - Stripe payment events

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_NAME` | Database name |
| `SECRET_KEY` | Flask secret key |
| `DUFFEL_API_TOKEN` | Duffel API token |
| `STRIPE_PUBLIC_KEY` | Stripe public key |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `ADMIN_USER` | Admin username |
| `ADMIN_PASSWORD` | Admin password |

See `.env.example` for complete list.

## Database Migrations

Create new migration:
```bash
alembic revision --autogenerate -m "Description"
```

Apply migrations:
```bash
alembic upgrade head
```

## Testing

Run tests:
```bash
pytest -v
```

With coverage:
```bash
pytest --cov=app --cov-report=html
```

## Monitoring

Access Prometheus metrics:
- Default: `http://localhost:8000/metrics`

View logs:
```bash
tail -f /tmp/agencia_app.log
```

## Common Issues

### Database Connection Error
- Verify PostgreSQL is running
- Check DB credentials in `.env`
- Ensure containers are up: `docker compose ps`

### Duffel Balance Insuficiente
- El pago Stripe puede quedar completado y la emisión en espera
- Usa el panel/admin de reintento de emisión cuando recargues balance
- Verifica token Duffel y saldo disponible

### Email Sending Fails
- Verify email service credentials in `.env`
- Check SMTP server availability
- Review app logs for specific errors

## Performance Optimization

- Redis caching enabled for flight searches
- Database query optimization with indexes
- Gunicorn worker limit: 4 (configurable)
- Static assets served via Nginx

## Security Notes

- All secrets in `.env` are required for production
- HTTPS enforced in production (via Nginx)
- CSRF protection enabled on all forms
- SQL injection prevented via SQLAlchemy ORM
- Password hashing with Werkzeug
- API rate limiting via Flask-Limiter

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit a pull request

## License

Proprietary - Viatges Carcaixent

## Support

For issues or questions:
1. Check app logs: `tail -f /tmp/agencia_app.log`
2. Review API responses in browser console
3. Contact development team

## Deployment Checklist

- [ ] `.env` configured with production credentials
- [ ] Database backed up
- [ ] Static files collected and optimized
- [ ] HTTPS certificates installed
- [ ] Database migrations applied
- [ ] Email service verified
- [ ] Payment credentials validated
- [ ] API rate limits configured
- [ ] Monitoring enabled
- [ ] Error logging configured

---

**Last Updated**: February 2025
