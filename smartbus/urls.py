"""
URL configuration for smartbus project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from .views import FrontendAppView

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),
    
    # API routes (all routes starting with /api/)
    path('api/', include('api.urls')),
    
    # Serve static assets (JS, CSS files from dist/assets/)
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'dist' / 'assets'}),
    
    # Serve root-level static files (vite.svg, etc.)
    re_path(r'^vite\.svg$', serve, {'document_root': settings.BASE_DIR / 'dist', 'path': 'vite.svg'}),
    
    # Catch-all pattern for frontend routes (must be last)
    # This serves index.html for all other routes, allowing React Router to work
    re_path(r'^.*$', FrontendAppView.as_view()),
]
