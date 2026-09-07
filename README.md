# SmartHealth

Sistema web para agendamento e gestão de consultas de uma clínica fictícia. Visitantes podem solicitar horários pela página pública; administradores e médicos acessam painéis separados para acompanhar a agenda e os atendimentos clínicos.

## Funcionalidades

- Agendamento público de consultas com validações de nome, CPF, e-mail, telefone, data e horário.
- Agenda por médico, com bloqueio de conflitos e limite de até seis meses-calendário à frente.
- Painel administrativo protegido por login, com filtros, paginação, reagendamento e alteração de status.
- Status da consulta limitados a `pendente`, `confirmado` e `cancelado`.
- Painel médico restrito às próprias consultas, com atendimento, solicitação de exames, receitas e prontuário.
- Conclusão de atendimento registrada separadamente do status da consulta.
- Oito especialidades e profissionais de demonstração carregados por seed.
- Páginas personalizadas para erros 403, 404 e 500 quando `DEBUG=False`.

## Stack

- Python 3.13
- Django 6.1.1
- SQLite
- Tailwind CSS e Alpine.js via CDN

## Pré-requisitos

- Python 3.13 ou superior instalado e disponível no terminal.
- Git, caso vá clonar o repositório.

Não há variáveis de ambiente obrigatórias para executar o projeto localmente.

## Instalação e execução

Clone o repositório e entre na pasta do projeto:

```bash
git clone <URL_DO_REPOSITORIO>
cd projeto_estagio_2026_2
```

Crie e ative um ambiente virtual.

No Windows com PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

No macOS ou Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Instale as dependências, crie as tabelas e carregue os dados de demonstração:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
```

O banco `db.sqlite3` não faz parte do repositório. Portanto, os comandos `migrate` e `seed_data` são necessários em uma cópia nova do projeto.

## Contas de demonstração

Após executar o seed, abra o shell do Django:

```bash
python manage.py shell
```

Cole o bloco abaixo. Ele cria ou atualiza as duas contas de demonstração e associa o usuário médico ao Dr. João Silva.

```python
from django.contrib.auth import get_user_model
from core.models import Especialidade, Medico

User = get_user_model()

admin, _ = User.objects.get_or_create(username="admin")
admin.email = "admin@smarthealth.test"
admin.is_staff = True
admin.is_superuser = True
admin.is_active = True
admin.set_password("adminpassword")
admin.save()

especialidade = Especialidade.objects.get(nome="Clínica geral")
medico, _ = Medico.objects.update_or_create(
    crm="123",
    defaults={
        "nome": "João Silva",
        "email": "jemail@email.com",
        "telefone": "123",
        "especialidade": especialidade,
        "ativo": True,
    },
)
usermedico, _ = User.objects.get_or_create(username="usermedico")
usermedico.email = "usermedico@smarthealth.test"
usermedico.is_staff = False
usermedico.is_superuser = False
usermedico.is_active = True
usermedico.set_password("medicopassword")
usermedico.save()

Medico.objects.filter(usuario=usermedico).exclude(pk=medico.pk).update(usuario=None)
medico.usuario = usermedico
medico.ativo = True
medico.save(update_fields=("usuario", "ativo"))
```

Saia do shell com `exit()` e inicie o servidor:

```bash
python manage.py runserver
```

Abra [http://127.0.0.1:8000/](http://127.0.0.1:8000/) no navegador.

| Perfil | Usuário | Senha | Painel |
|---|---|---|---|
| Superadmin | `admin` | `adminpassword` | [http://127.0.0.1:8000/painel/](http://127.0.0.1:8000/painel/) |
| Médico | `usermedico` | `medicopassword` | [http://127.0.0.1:8000/painel/](http://127.0.0.1:8000/painel/) |

Essas credenciais são exclusivamente para demonstração local. Não as use em ambiente público ou de produção.

## Regras de negócio principais

- A agenda funciona de segunda a sexta, das 8h às 11h e das 13h às 17h; aos sábados, das 8h às 11h.
- Não é possível agendar no passado, além de seis meses-calendário ou em horário já ocupado pelo mesmo médico.
- Toda solicitação nasce com status `pendente`.
- O administrador pode usar somente `pendente`, `confirmado` e `cancelado` como status.
- A conclusão de uma consulta não altera seu status: ela registra a data de conclusão e bloqueia novas alterações clínicas.
- O médico visualiza apenas as consultas associadas ao seu próprio cadastro.

## Rotas úteis

| Rota | Descrição |
|---|---|
| `/` | Página pública e formulário de agendamento |
| `/login/` | Login para os painéis |
| `/painel/` | Painel administrativo ou médico, conforme o perfil autenticado |
| `/admin/` | Administração padrão do Django |

## Testes e verificações

Para executar a suíte de testes automatizados:

```bash
python manage.py test
```

Para verificar a configuração do Django:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Desenvolvimento local

O projeto inicia com `DEBUG=True`. Para testar as páginas personalizadas de erro 403, 404 e 500, altere temporariamente `DEBUG` para `False` em `config/settings.py` e mantenha um host local permitido, por exemplo:

```python
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
```
