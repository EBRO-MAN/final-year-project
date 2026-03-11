# Django-sheep-ES 🐑

A Django-based project designed to demonstrate **role-based authentication, permissions, and scalable architecture** with Elasticsearch integration. This repository provides a clean, maintainable structure for backend developers who want to build secure, extensible systems while experimenting with modern search capabilities.



## 🚀 Features

- **Custom User Model** – Flexible authentication with role-based access control.  
- **Permissions System** – Fine-grained authorization for different user roles.  
- **Elasticsearch Integration** – Efficient search and indexing for scalable applications.  
- **Modular Project Layout** – Clear separation of concerns for maintainability.  
- **API Endpoints** – RESTful design for easy frontend integration.  
- **Template & Static Management** – Organized paths for reusable UI components.  



## 📂 Project Structure

```
Django-sheep-ES/
│── sheep/                # Core Django app
│── templates/            # HTML templates
│── static/               # Static assets (CSS, JS, images)
│── requirements.txt      # Python dependencies
│── manage.py             # Django project manager
│── README.md             # Project documentation
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.10+
- Django 4.x
- Elasticsearch (latest stable version)
- pip / virtualenv

### Setup
```bash
# Clone the repository
git clone https://github.com/EBRO-MAN/Django-sheep-ES.git
cd Django-sheep-ES

# Create virtual environment
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```



## 🔑 Configuration

- **Database**: Update `settings.py` with your preferred database (default: SQLite).  
- **Elasticsearch**: Ensure Elasticsearch is running locally or remotely, and configure connection settings in `settings.py`.  
- **Environment Variables**: Use `.env` file for secrets (e.g., `SECRET_KEY`, DB credentials).  



## 📡 API Endpoints (Examples)

- `POST /auth/login/` – User login  
- `POST /auth/register/` – User registration  
- `GET /sheep/` – List sheep records (requires authentication)  
- `POST /sheep/` – Add new sheep (role-based permission required)  



## 🧪 Testing

```bash
python manage.py test
```

Unit tests cover authentication, permissions, and search functionality.



## 🤝 Contributing

Contributions are welcome!  
1. Fork the repo  
2. Create a feature branch (`git checkout -b feature-name`)  
3. Commit changes (`git commit -m "Add feature"`)  
4. Push to branch (`git push origin feature-name`)  
5. Open a Pull Request  


## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.



## 👨‍💻 Author

Developed by **[Ebrahim](https://github.com/EBRO-MAN)**  
Passionate about backend development, authentication systems, and scalable architectures.



