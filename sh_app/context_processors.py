# sh_app/context_processors.py
from .services1 import get_ram_capacity_info

def ram_capacity_info(request):
    def get_capacity_info(ram):
        return get_ram_capacity_info(ram)  # No need for start_date parameter
    return {'get_capacity_info': get_capacity_info}