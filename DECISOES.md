## Tema e stack

Desenvolvi um sistema de agendamento e gerenciamento de consultas em uma clínica geral fictícia, a SmartHealth.

## Stack

 - **Django:** O Django foi escolhido por reunir recursos essenciais ao projeto, como autenticação, sessões, proteção CSRF, ORM, migrations e validações, reduzindo a necessidade de implementar infraestrutura básica e permitiu concentrar o desenvolvimento nas regras de negócio e no controle de permissões.

 - **SQLite:** O SQLite foi adotado pela simplicidade de configuração e execução local, sendo suficiente para o volume de dados esperado, em contrapartida, possui limitações de concorrência e escalabilidade.

 - **Tailwind CSS via CDN:** agilizou a construção de uma interface responsiva sem exigir configuração de build, ao custo de menor otimização e controle sobre os estilos gerados quando comparado ao uso com processo de compilação.

 - **O Alpine.js via CDN:** foi utilizado para interações simples, como modais e abas, evitando a complexidade de uma SPA, apesar de possuir menos recursos para interfaces altamente interativas.

## O que adicionei além do pedido

- **Agenda com horários disponíveis e prevenção de conflitos**: o visitante não informa um horário livremente. O sistema apresenta somente horários disponíveis, valida novamente no servidor e impede no banco duas consultas pendentes ou confirmadas para o mesmo médico no mesmo horário. A agenda atende em dias úteis e aos sábados até 14h.
- **Perfis de acesso**: além do superadmin exigido, criei o perfil de médico. Ele vê somente as próprias consultas e não acessa dados administrativos, o Django Admin ou consultas de outros profissionais.
- **Atendimento clínico**: médicos registram sintomas, diagnóstico opcional, conduta e observações, solicitam exames, emitem receitas e concluem apenas consultas confirmadas que já tenham atendimento registrado.
- **Gestão administrativa ampliada**: detalhes, alteração de status, reagendamento com bloqueio de conflito, exclusão restrita a consultas canceladas e gestão de médicos. O cadastro médico cria usuário sem privilégios administrativos e gera senha temporária, exibida uma única vez.
- **Usabilidade**: busca por nome, filtros e paginação nos dois painéis. A busca atualiza apenas a lista com debounce e mantém fallback sem JavaScript; notificações de sucesso fecham automaticamente.

## O que decidi não fazer

- **Financeiro e convênios**: removi o módulo completo, incluindo modelos, tabelas, seed e referências administrativas. Cobrança, estorno e auditoria exigiriam regras próprias e não seriam bem resolvidos como complemento superficial.
- **Relatórios, e-mails e integrações externas**: priorizei o fluxo clínico central e a execução local simples.
- **CRUD administrativo completo de pacientes**: o superadmin consulta os dados necessários no contexto das consultas, um módulo independente de pacientes não era essencial ao fluxo escolhido.

## Onde tive dificuldade

A evolução do prontuário exigiu decidir o que é dado permanente e o que é registro de uma consulta. A solução foi manter paciente, atendimento, exames e receitas em entidades próprias, e gerar o prontuário a partir delas. Assim, reduzi a duplicidade e o prontuário não pode ser atualizado após a conclusão da consulta.

Também houve ajustes de interface guiados por teste manual, em que mensagens de erro dos formulários quebravam o layout quando todos os campos eram renderizados com `as_p`, então, passei a renderizar manualmente os inputs com widgets do Django nos formulários público e de cadastro de médico.

## Uso de IA

1. **O que você delegou para a IA e o que fez à mão, e por quê**

Deleguei à IA atividades de implementação assistida e diagnóstico de erros. Utilizei principalmente como ferramenta aceleradora do processo de desenvolvimento: construí manualmente a base do projeto e, a partir de prompts detalhados, solicitei complementos pontuais de código quando considerei necessário.  

2. **Uma vez em que a IA te deu algo ruim ou errado: o que era, como você percebeu, e o que fez no lugar**

Em uma alteração do prontuário, a IA sugeriu recriar uma migration já relacionada ao histórico do banco, que ocasionou incompatibilidade entre o estado registrado em `django_migrations` e a estrutura esperada, resultando em erro durante o migrate. Identifiquei o problema ao executar a migration, restaurei a migration histórica correta e criei uma nova migration incremental para a mudança atual.

3. **Uma decisão que você tomou contra a sugestão da IA, e o motivo**

Decidi evitar a criação de páginas completas para conteúdos que pertenciam a telas já existentes. A IA sugeriu inicialmente separar essas funcionalidades em páginas próprias, mas isso aumentaria a navegação e duplicaria estrutura visual. Preferi utilizar partials para formulários e listagens reutilizáveis, mantendo funcionalidades relacionadas no mesmo fluxo e facilitando atualizações assíncronas.
