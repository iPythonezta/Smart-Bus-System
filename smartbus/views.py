"""
Views for serving the React frontend application.
"""
from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator


@method_decorator(never_cache, name='dispatch')
class FrontendAppView(TemplateView):
    """
    Serves the compiled frontend single page application (SPA).
    This view serves index.html for all frontend routes,
    allowing React Router to handle client-side routing.
    """
    template_name = 'index.html'
