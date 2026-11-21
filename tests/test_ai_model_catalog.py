import requests

def test_ai_model_catalog_lifecycle():
    s = requests.Session()
    # Login as admin
    login_res = s.post('http://localhost:5000/api/auth/login', json={'username': 'admin', 'password': 'admin'})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    print("[PASS] Admin login succeeded")

    # 1. Fetch admin AI models
    r = s.get('http://localhost:5000/api/admin/ai-models')
    assert r.status_code == 200, f"Admin GET failed: {r.text}"
    # Clean up prior test model if present
    for m in r.json().get('models', []):
        if 'qwen' in m.get('model_id', ''):
            s.delete(f"http://localhost:5000/api/admin/ai-models/{m['id']}")

    r = s.get('http://localhost:5000/api/admin/ai-models')
    initial_count = len(r.json().get('models', []))
    print(f"[PASS] Admin catalog loaded ({initial_count} models)")

    # 2. Add custom AI model (ZenMux / OpenRouter)
    new_model = {
        'provider': 'openrouter',
        'model_id': 'openrouter/qwen/qwen-2.5-coder-32b-instruct',
        'display_name': 'Qwen 2.5 Coder 32B',
        'badge': '💡',
        'description': 'Specialized Code & IaC LLM',
        'is_enabled': True,
        'is_default': False
    }
    add_res = s.post('http://localhost:5000/api/admin/ai-models', json=new_model)
    assert add_res.status_code in (200, 201), f"Admin POST failed: {add_res.text}"
    added_model = add_res.json().get('model', {})
    added_id = added_model['id']
    print(f"[PASS] Added new AI model: {added_model['display_name']} (ID {added_id})")

    # 3. Toggle model disabled
    toggle_res = s.put(f'http://localhost:5000/api/admin/ai-models/{added_id}', json={'is_enabled': False})
    assert toggle_res.status_code == 200
    assert toggle_res.json()['model']['is_enabled'] is False
    print("[PASS] Disabled model successfully")

    # Verify public endpoint does NOT show disabled model
    pub_res = s.get('http://localhost:5000/api/ai-models')
    active_ids = [m['id'] for m in pub_res.json().get('models', [])]
    assert added_id not in active_ids, "Disabled model should NOT appear in public Copilot endpoint"
    print("[PASS] Public Copilot endpoint properly filters out disabled model")

    # 4. Toggle model back to enabled
    toggle_res2 = s.put(f'http://localhost:5000/api/admin/ai-models/{added_id}', json={'is_enabled': True})
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()['model']['is_enabled'] is True
    pub_res2 = s.get('http://localhost:5000/api/ai-models')
    active_ids2 = [m['id'] for m in pub_res2.json().get('models', [])]
    assert added_id in active_ids2, "Enabled model must appear in public Copilot endpoint"
    print("[PASS] Re-enabled model appears immediately in public Copilot endpoint")

    # 5. Set as default model
    def_res = s.post(f'http://localhost:5000/api/admin/ai-models/{added_id}/default')
    assert def_res.status_code == 200
    pub_res3 = s.get('http://localhost:5000/api/ai-models')
    def_model = next(m for m in pub_res3.json().get('models', []) if m['is_default'])
    assert def_model['id'] == added_id, "New model should be the default"
    print(f"[PASS] Default model switched to: {def_model['display_name']}")

    # Restore Gemini 2.0 Flash as default
    s.post('http://localhost:5000/api/admin/ai-models/1/default')
    print("[PASS] Restored Gemini 2.0 Flash as default model")

    # 6. Delete test model
    del_res = s.delete(f'http://localhost:5000/api/admin/ai-models/{added_id}')
    assert del_res.status_code == 200
    print(f"[PASS] Deleted custom model: {del_res.json().get('message')}")

    # Final check
    final_admin_res = s.get('http://localhost:5000/api/admin/ai-models')
    assert len(final_admin_res.json().get('models', [])) == initial_count
    print(f"[PASS] Catalog returned to baseline {initial_count} models")

if __name__ == '__main__':
    test_ai_model_catalog_lifecycle()
    print("\nALL DYNAMIC AI MODEL LIFECYCLE TESTS PASSED! ✨")
