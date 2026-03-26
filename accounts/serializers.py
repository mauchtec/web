from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

ROLE_MAPPING = {
    "operator": {"group": "Operator", "is_staff": False, "is_superuser": False},
    "security_manager": {"group": "SecurityManager", "is_staff": True, "is_superuser": False},
    "admin": {"group": "Admin", "is_staff": True, "is_superuser": False},
    "auditor": {"group": "Auditor", "is_staff": False, "is_superuser": False},
    "superuser": {"group": "Admin", "is_staff": True, "is_superuser": True},
}


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(allow_blank=True, required=False)
    last_name = serializers.CharField(allow_blank=True, required=False)
    role = serializers.ChoiceField(choices=[(key, key.replace("_", " ").title()) for key in ROLE_MAPPING.keys()])

    def create(self, validated_data):
        role = validated_data.pop("role")
        role_config = ROLE_MAPPING[role]
        User = get_user_model()
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        user.is_staff = role_config["is_staff"]
        user.is_superuser = role_config["is_superuser"]
        user.save()

        if role_config["group"]:
            group, _ = Group.objects.get_or_create(name=role_config["group"])
            user.groups.add(group)

        return user
