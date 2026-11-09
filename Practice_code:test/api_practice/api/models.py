from django.db import models

# Define the data your API will serve here.
class ClassifiedFile(models.Model):
    codename = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    contents = models.TextField()
    clearance_level = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.codename