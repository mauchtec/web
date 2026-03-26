from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from GateCore.services.access_evaluator import evaluate_access
from GateCore.services.hardware_interface import GateHardwareInterface

User = get_user_model()

class AccessRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        location = request.data.get('location')
        method = request.data.get('method', None)
        if not location:
            return Response({'error': 'Location is required.'}, status=400)
        granted, reason = evaluate_access(user, location, method)
        if granted:
            GateHardwareInterface().open_gate(location)
        return Response({'granted': granted, 'reason': reason})
