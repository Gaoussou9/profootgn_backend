# clubs/views_api.py
import re
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Club, StaffMember
from .serializers import ClubMinimalSerializer, StaffSerializer

class ClubMinimalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Club.objects.all().order_by('name')
    serializer_class = ClubMinimalSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]


ROLE_MAP = {
    'coach': 'COACH', 'entraîneur': 'COACH', 'entraineur': 'COACH',
    'principal': 'COACH', 'adjoint': 'ASSIST_COACH', 'président': 'PRESIDENT',
    'president': 'PRESIDENT', 'directeur': 'DIRECTOR', 'manager': 'TEAM_MANAGER',
    'kiné': 'PHYSIO', 'kine': 'PHYSIO', 'gk': 'GK_COACH', 'gardien': 'GK_COACH',
    'analyste': 'ANALYST', 'intendant': 'KIT_MANAGER',
}
def normalize_role(txt):
    if not txt: return 'COACH'
    key = txt.strip().lower()
    return ROLE_MAP.get(key, key.upper().replace(' ', '_'))

STAFF_RE = re.compile(
    r"^\s*(?P<name>[^|]+?)\s*(?:\|\s*(?P<role>[^|]+))?\s*(?:\|\s*(?P<phone>[^|]+))?\s*(?:\|\s*(?P<email>[^|]+))?\s*$"
)

class StaffViewSet(viewsets.ModelViewSet):
    queryset = StaffMember.objects.select_related('club').all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        club_id = self.request.query_params.get('club')
        role = self.request.query_params.get('role')
        q = self.request.query_params.get('q')
        if club_id: qs = qs.filter(club_id=club_id)
        if role: qs = qs.filter(role=role)
        if q: qs = qs.filter(full_name__icontains=q)
        return qs.order_by('role','full_name')

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def quick_bulk_create(self, request):
        """
        body: {"club_id": 3, "text": "Nom | Rôle | Téléphone | Email", "dry_run": true}
        """
        club_id = request.data.get('club_id')
        text = request.data.get('text', '')
        dry = bool(request.data.get('dry_run', False))
        if not club_id:
            return Response({'detail':'club_id requis.'}, status=400)
        try:
            club = Club.objects.get(pk=club_id)
        except Club.DoesNotExist:
            return Response({'detail':'Club introuvable.'}, status=404)

        created, errors, parsed = [], [], []
        for i, raw in enumerate([l for l in text.splitlines() if l.strip()], start=1):
            m = STAFF_RE.match(raw)
            if not m:
                errors.append({'line': i, 'raw': raw, 'error': 'Format invalide'})
                continue
            item = {
                'full_name': m.group('name').strip(),
                'role': normalize_role(m.group('role')),
                'phone': (m.group('phone') or '').strip(),
                'email': (m.group('email') or '').strip(),
            }
            parsed.append(item)
            if not dry:
                s = StaffMember.objects.create(club=club, **item)
                created.append(s.id)

        return Response({
            'summary': {'lines': len(parsed)+len(errors), 'created': len(created), 'errors': len(errors)},
            'created_ids': created, 'errors': errors, 'parsed': parsed
        }, status=200 if dry else status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def upload_photo(self, request, pk=None):
        obj = self.get_object()
        file = request.FILES.get('photo')
        if not file:
            return Response({'detail':'photo requise.'}, status=400)
        obj.photo = file
        obj.save(update_fields=['photo'])
        return Response(StaffSerializer(obj).data, status=200)
