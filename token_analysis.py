import tiktoken


consulta_es = (
    "Desde la última actualización, al iniciar sesión en la aplicación móvil con una "
    "cuenta existente aparece el error 401. El problema ocurre en Android y comenzó "
    "esta mañana."
)
consulta_en = (
    "Since the latest update, logging into the mobile application with an existing "
    "account returns a 401 error. The issue occurs on Android and started this morning."
)

encoding = tiktoken.encoding_for_model("gpt-4o")

print(f"Español: {len(encoding.encode(consulta_es))} tokens")
print(f"Inglés: {len(encoding.encode(consulta_en))} tokens")
