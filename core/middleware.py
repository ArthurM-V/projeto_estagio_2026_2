import time
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import logout

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            tempo_atual = time.time()
            ult_atividade = request.session.get('last_activity')

            if ult_atividade:
                tempo_decorrido = tempo_atual - ult_atividade

                if tempo_decorrido > settings.SESSION_IDLE_TIMEOUT:
                    logout(request)
                    return redirect('session_expired')

            request.session['last_activity'] = tempo_atual

        return self.get_response(request)
